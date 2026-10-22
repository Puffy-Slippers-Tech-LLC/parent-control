"""Fail-closed fixture transactions keep input behind attempt-bound readiness.

Resource review: pytest-private disk roots and in-memory lease, SSH and native
doubles only. No subprocess, VM, display, bus, socket, service, compiler, shared
cache or installed product. Small bounded I/O permits compatible unit overlap.
"""
import copy
import base64
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from tools import fixture_manifest, fixture_provision as provision
from tools import fixture_execution
from tools import artifact_inputs, test_retention as retention, test_storage as storage
from tests.support.fixture_bundles import compiler_record, environment_record, inert_elf
from tests.fixtures import fixture_guest as guest, native_trust, native_assets


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bundle_input(target='ubuntu'):
    """Trusted input-reader double; bundle authentication has its own regressions."""
    payloads, members = {}, {}
    for key, declaration in fixture_manifest.declarations().items():
        source = declaration['source']
        payload = source if isinstance(source, bytes) else source.encode() + b' inert bytes\n'
        payloads[key] = payload
        members[key] = {name: value for name, value in declaration.items() if name != 'source'}
        members[key].update(length=len(payload), sha256=sha(payload))
    manifest = {
        'schema': fixture_manifest.SCHEMA, 'build_identity': 'b' * 64,
        'inputs': {'target': {'os': target,
                              'release': '26.04' if target == 'ubuntu' else '44',
                              'architecture': 'x86_64'}},
        'members': members, 'absences': fixture_manifest.ABSENCES, 'abi': {},
    }
    return {'manifest': manifest, 'payloads': payloads, 'content_identity': 'c' * 64}


class FilesystemBoundary:
    """Finite guest/native double with real files and recorded cleanup ownership."""
    def __init__(self, root, registered, target):
        self.root, self.registered, self.target = root, registered, copy.deepcopy(target)
        self.calls, self.writes, self.metadata, self.native = [], [], {}, {}
        self.fail, self.lost_reply, self.corrupt_readback = None, None, None
        self.accounts = {
            role: {'uid': 1000 + index, 'gid': 1000 + index, 'home': '/home/' + role}
            for index, role in enumerate(('child', 'other', 'parent'))}
        self.accounts['system'] = {'uid': 0, 'gid': 0, 'home': '/root'}

    def path(self, name):
        return self.root / name.removeprefix('/')

    def call(self, action, request, payloads=None):
        self.calls.append((action, copy.deepcopy(request)))
        if self.fail == action:
            raise OSError('private-canary failure at ' + action)
        members = request.get('members', {})
        if action == 'inspect':
            reply = {'accounts': copy.deepcopy(self.accounts), 'target': self.target}
        elif action == 'preflight':
            for item in members.values():
                path = self.path(item['destination'])
                if path.is_symlink() or path.exists() and (
                        not path.is_file() or path.read_bytes() != self.payload(item)
                        or self.metadata.get(item['destination']) != self.expected(item)):
                    raise ValueError('foreign-or-modified-destination')
            for name in request['absences']:
                if self.path(name).exists() or self.path(name).is_symlink():
                    raise ValueError('required-absence')
            reply = {'ok': True}
        elif action in ('reserve', 'stage'):
            assert request['staging'] in self.registered, 'unregistered staging mutation'
            stage = self.path(request['staging'])
            if action == 'reserve':
                stage.mkdir(parents=True, mode=0o700)
                info = stage.stat()
                reply = {'ok': True, 'identity': [info.st_dev, info.st_ino]}
            else:
                assert set(payloads) == set(members), 'unselected bytes sent to guest'
                for key, data in payloads.items():
                    (stage / key).write_bytes(data)
                reply = {'ok': True, 'identities': {
                    key: [(stage / key).stat().st_dev, (stage / key).stat().st_ino]
                    for key in payloads}}
            self.writes.append(action)
        elif action == 'place':
            for key, item in members.items():
                path = self.path(item['destination'])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((self.path(request['staging']) / key).read_bytes())
                path.chmod(item['mode'])
                self.metadata[item['destination']] = self.expected(item)
            self.writes.append(action)
            reply = {'ok': True}
        elif action == 'activate':
            self.native = {item['destination']: item['native_action']
                           for item in members.values() if item['native_action'] != 'none'}
            self.writes.append(action)
            reply = {'ok': True}
        elif action == 'readback':
            files = {key: dict(sha256=sha(self.path(item['destination']).read_bytes()),
                               length=self.path(item['destination']).stat().st_size,
                               **self.metadata[item['destination']])
                     for key, item in members.items()}
            if self.corrupt_readback:
                files[next(iter(files))][self.corrupt_readback] = -1
            reply = {'files': files, 'native': True, 'labels': True}
        elif action == 'witness':
            reply = {'ready': True}
        elif action == 'clean':
            stage = self.path(request['staging'])
            for child in stage.iterdir():
                child.unlink()
            stage.rmdir()
            self.writes.append(action)
            reply = {'ok': True}
        else:
            raise AssertionError('unexpected operation ' + action)
        if self.lost_reply == action:
            raise TimeoutError('private-canary reply lost at ' + action)
        return reply

    def payload(self, item):
        return next(data for key, data in self.input['payloads'].items()
                    if self.input['manifest']['members'][key]['sha256'] == item['sha256'])

    @staticmethod
    def expected(item):
        return {name: item[name] for name in ('mode', 'uid', 'gid')}


@pytest.fixture
def rig(tmp_path):
    data, registered = bundle_input(), []
    lease = SimpleNamespace(fd=42, state={'phase': 'running', 'domain_id': 71,
        'domain_uuid': 'f95890e1-88e7-4779-8ae3-53fdcc34330a', 'run': 'a' * 32},
        guard=Mock(), restore=Mock(), cleanup=Mock())
    transport = Mock(config={key: lease.state[key]
                            for key in ('domain_id', 'domain_uuid', 'run')})
    transport.call.return_value = ('d' * 64 + '\n').encode()
    boundary = FilesystemBoundary(tmp_path, registered, data['manifest']['inputs']['target'])
    boundary.input = data
    reader = Mock(return_value=data)
    control = provision.Provisioner(lease, transport, register_staging=registered.append,
                                   boundary=boundary, input_reader=reader)
    return SimpleNamespace(control=control, boundary=boundary, input=data,
                           reader=reader, registered=registered, lease=lease,
                           transport=transport, selection={'build_identity': 'b' * 64},
                           attempt='e' * 32)


def execute(rig, subsets=('mechanical',)):
    return rig.control.provision(rig.selection, list(subsets), attempt_id=rig.attempt)


def assert_terminal(rig):
    assert rig.control.failed
    calls = copy.deepcopy(rig.boundary.calls)
    with pytest.raises(Exception):
        execute(rig)
    assert rig.boundary.calls == calls
    rig.lease.restore.assert_not_called()
    rig.lease.cleanup.assert_not_called()


def test_environment_wait_observes_only_and_never_releases_readiness(rig):
    result = rig.control.wait_environment()
    assert result['accounts'] == rig.boundary.accounts
    assert [action for action, _ in rig.boundary.calls] == ['inspect']
    assert not rig.registered and not rig.boundary.writes
    rig.reader.assert_not_called()
    with pytest.raises(ValueError, match='readiness-required'):
        rig.control.require_ready(None)


def test_environment_wait_failure_poisons_existing_lease(rig):
    rig.boundary.fail = 'inspect'
    with pytest.raises(OSError):
        rig.control.wait_environment()
    assert_terminal(rig)
    assert not rig.registered


@pytest.mark.parametrize('subsets', [(), ('mechanical',), ('native',),
                                    ('activity', 'trusted-hard'), ('catalogue',)])
def test_selected_membership_exact_native_actions_and_private_staging(rig, subsets):
    unrelated = rig.boundary.path('/etc/product-policy')
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b'preserve product and vendor policy')
    ready = execute(rig, subsets)
    request = next(request for action, request in rig.boundary.calls if action == 'readback')
    assert set(request['members']) == set(fixture_manifest.select(list(subsets)))
    for key, item in request['members'].items():
        path = rig.boundary.path(item['destination'])
        assert path.read_bytes() == rig.input['payloads'][key]
        assert path.stat().st_mode & 0o777 == item['mode']
        assert rig.boundary.metadata[item['destination']] == rig.boundary.expected(item)
    assert rig.boundary.native == {
        item['destination']: item['native_action'] for item in request['members'].values()
        if item['native_action'] != 'none'}
    assert unrelated.read_bytes() == b'preserve product and vendor policy'
    assert rig.control.require_ready(ready) == ready
    assert len(rig.registered) == 1
    assert not rig.boundary.path(rig.registered[0]).exists()


def test_identical_repeat_verifies_without_writes_or_registration(rig):
    first = execute(rig)
    writes, registered = rig.boundary.writes[:], rig.registered[:]
    rig.boundary.calls.clear()
    assert execute(rig) == first
    assert rig.boundary.writes == writes and rig.registered == registered
    assert [action for action, _ in rig.boundary.calls] == [
        'inspect', 'preflight', 'readback', 'witness']


def test_installed_hard_reboot_renews_only_readiness_and_preserves_scenario_mutations(rig):
    first = execute(rig, ('trusted-hard',))
    scenario = rig.boundary.path('/home/child/scenario-document')
    scenario.parent.mkdir(parents=True)
    scenario.write_bytes(b'preserve deliberate scenario version')
    writes, registered = rig.boundary.writes[:], rig.registered[:]
    rig.boundary.calls.clear()
    rig.reader.reset_mock()
    rig.transport.call.return_value = ('f' * 64 + '\n').encode()
    renewed = rig.control.renew_after_reboot(first)
    assert renewed.binding == {**first.binding, 'boot_sha256': 'f' * 64}
    assert renewed.files == first.files
    assert rig.control.require_ready(renewed) == renewed
    assert [action for action, _ in rig.boundary.calls] == [
        'inspect', 'preflight', 'readback', 'witness']
    assert all(request['repeat'] for _, request in rig.boundary.calls)
    assert rig.boundary.writes == writes and rig.registered == registered
    assert scenario.read_bytes() == b'preserve deliberate scenario version'
    rig.reader.assert_not_called()
    with pytest.raises(ValueError, match='readiness-required'):
        rig.control.require_ready(first)
    assert_terminal(rig)


@pytest.mark.parametrize('fault', ['same-boot', 'foreign-receipt', 'failed', 'subset',
                                  'fedora', 'changed-accounts', 'changed-target',
                                  'modified', 'missing', 'preflight', 'readback', 'witness'])
def test_installed_reboot_renewal_refuses_without_writes_or_repair(rig, fault):
    ready = execute(rig, ('mechanical',) if fault == 'subset' else ('trusted-hard',))
    writes, registered = rig.boundary.writes[:], rig.registered[:]
    rig.boundary.calls.clear()
    rig.transport.call.return_value = ('f' * 64 + '\n').encode()
    if fault == 'same-boot':
        rig.transport.call.return_value = ('d' * 64 + '\n').encode()
    elif fault == 'foreign-receipt':
        ready.binding['attempt_id'] = 'foreign-attempt'
    elif fault == 'failed':
        rig.control.failed = True
    elif fault == 'fedora':
        rig.control._request['target'] = {'os': 'fedora', 'release': '44', 'architecture': 'x86_64'}
    elif fault == 'changed-accounts':
        rig.boundary.accounts['child']['uid'] += 10
    elif fault == 'changed-target':
        rig.boundary.target['architecture'] = 'aarch64'
    elif fault in ('modified', 'missing'):
        member = next(iter(rig.control._request['members'].values()))
        path = rig.boundary.path(member['destination'])
        if fault == 'missing':
            path.unlink()
        else:
            path.write_bytes(b'preserve changed scenario bytes')
    elif fault in ('preflight', 'readback', 'witness'):
        rig.boundary.fail = fault
    with pytest.raises((ValueError, OSError, KeyError)):
        rig.control.renew_after_reboot(ready)
    assert rig.boundary.writes == writes and rig.registered == registered
    assert_terminal(rig)


@pytest.mark.parametrize('fault', ['missing', 'incompatible'])
def test_invalid_input_fails_before_guest_mutation(rig, fault):
    if fault == 'missing':
        rig.reader.side_effect = FileNotFoundError('private-canary absent input')
    else:
        rig.input['manifest']['inputs']['target']['architecture'] = 'aarch64'
    with pytest.raises(Exception):
        execute(rig)
    assert not rig.boundary.writes and not rig.registered
    assert_terminal(rig)


@pytest.mark.parametrize('fault', ['foreign', 'modified', 'symlink', 'directory', 'absence'])
def test_destination_refusal_precedes_all_mutation(rig, fault):
    member = next(iter(fixture_manifest.select(['mechanical']).values()))
    path = rig.boundary.path('/usr/local/bin/onpc-test-catalog-fallback'
                             if fault == 'absence' else member['destination'])
    path.parent.mkdir(parents=True)
    if fault == 'symlink':
        path.symlink_to(path.parent / 'missing')
    elif fault == 'directory':
        path.mkdir()
    else:
        key = next(iter(fixture_manifest.select(['mechanical'])))
        path.write_bytes(rig.input['payloads'][key] if fault == 'foreign'
                         else b'preserve foreign bytes')
        if fault == 'modified':
            rig.boundary.metadata[str('/' + path.relative_to(rig.boundary.root).as_posix())] = {
                'mode': member['mode'], 'uid': 0, 'gid': 0}
    with pytest.raises(Exception):
        execute(rig, ('catalogue',) if fault == 'absence' else ('mechanical',))
    assert not rig.boundary.writes and not rig.registered
    assert path.is_symlink() if fault == 'symlink' else path.exists()
    assert_terminal(rig)


@pytest.mark.parametrize('phase', ['reserve', 'stage', 'place', 'activate', 'readback', 'witness', 'clean'])
@pytest.mark.parametrize('lost_reply', [False, True])
def test_failure_or_uncertain_reply_is_terminal_and_recovery_owns_staging(rig, phase, lost_reply):
    setattr(rig.boundary, 'lost_reply' if lost_reply else 'fail', phase)
    with pytest.raises((OSError, TimeoutError)):
        execute(rig)
    assert len(rig.registered) == 1
    actions = [action for action, _ in rig.boundary.calls]
    assert actions.count(phase) == 1 and actions[-1] == phase
    assert 'clean' not in actions or phase == 'clean'
    if phase not in ('reserve', 'clean') or lost_reply and phase == 'reserve':
        assert rig.boundary.path(rig.registered[0]).exists()
    assert_terminal(rig)


@pytest.mark.parametrize('field', ['sha256', 'length', 'mode', 'uid', 'gid'])
def test_independent_readback_mismatch_releases_no_readiness(rig, field):
    rig.boundary.corrupt_readback = field
    with pytest.raises(Exception):
        execute(rig)
    assert [action for action, _ in rig.boundary.calls][-1] == 'readback'
    assert_terminal(rig)


@pytest.mark.parametrize('change', ['boot', 'vm', 'run', 'attempt'])
def test_stale_readiness_never_authorizes_scenario_input(rig, change):
    ready = execute(rig)
    if change == 'boot':
        rig.transport.call.return_value = ('f' * 64 + '\n').encode()
    elif change == 'vm':
        rig.transport.config['domain_uuid'] = 'foreign-vm'
    elif change == 'run':
        rig.transport.config['run'] = 'f' * 32
    else:
        other = copy.deepcopy(ready)
        other.binding['attempt_id'] = 'f' * 32
        ready = other
    scenario_input = Mock()
    with pytest.raises(Exception):
        rig.control.require_ready(ready)
        scenario_input()
    scenario_input.assert_not_called()
    assert_terminal(rig)


@pytest.mark.parametrize('fault', ['closed', 'phase', 'ownership', 'domain', 'guard'])
def test_lease_refusal_blocks_every_guest_operation(rig, fault):
    if fault == 'closed':
        rig.lease.fd = None
    elif fault == 'phase':
        rig.lease.state['phase'] = 'isolated'
    elif fault == 'ownership':
        rig.transport.config['run'] = 'f' * 32
    elif fault == 'domain':
        rig.transport.config['domain_id'] = 72
    else:
        rig.lease.guard.side_effect = ValueError('ownership lost')
    with pytest.raises(Exception):
        execute(rig)
    assert rig.boundary.calls == [] and rig.registered == []
    rig.transport.call.assert_not_called()
    assert_terminal(rig)


@pytest.mark.parametrize('fault', ['subsets', 'payload', 'declaration', 'content'])
def test_selected_input_cannot_inject_paths_actions_or_wrong_bytes(rig, fault):
    key = next(iter(fixture_manifest.select(['mechanical'])))
    subsets = ['mechanical']
    if fault == 'subsets':
        subsets = ['../../foreign']
    elif fault == 'payload':
        rig.input['payloads'][key] += b'changed'
    elif fault == 'declaration':
        rig.input['manifest']['members'][key]['destination'] = '/etc/product-policy'
    else:
        rig.input['content_identity'] = 'invalid'
    with pytest.raises(Exception):
        execute(rig, subsets)
    assert rig.boundary.calls == [] and rig.registered == []
    assert_terminal(rig)


def test_registration_failure_prevents_reservation_and_preserves_diagnostic(rig, tmp_path):
    diagnostic = tmp_path / 'owned-diagnostic'
    diagnostic.write_bytes(b'first failure evidence')
    rig.control.register_staging = Mock(side_effect=OSError('journal unavailable'))
    with pytest.raises(OSError, match='journal unavailable'):
        execute(rig)
    assert [action for action, _ in rig.boundary.calls] == ['inspect', 'preflight']
    assert rig.boundary.writes == []
    assert diagnostic.read_bytes() == b'first failure evidence'
    assert_terminal(rig)


def test_empty_or_foreign_receipt_cannot_open_input_boundary(rig):
    foreign = provision.Readiness({'attempt_id': rig.attempt}, {})
    with pytest.raises(ValueError):
        rig.control.require_ready(foreign)
    assert rig.boundary.calls == [] and not rig.registered
    assert_terminal(rig)


def test_changed_subset_is_terminal_without_guest_contraction(rig):
    execute(rig, ('mechanical', 'trusted-hard'))
    calls, writes = rig.boundary.calls[:], rig.boundary.writes[:]
    with pytest.raises(ValueError, match='changed-request'):
        execute(rig, ('mechanical',))
    assert rig.boundary.calls == calls and rig.boundary.writes == writes
    assert_terminal(rig)


@pytest.mark.parametrize('lost_reply', [False, True])
def test_fresh_provisioner_cannot_replay_poisoned_lease(rig, lost_reply):
    setattr(rig.boundary, 'lost_reply' if lost_reply else 'fail', 'place')
    with pytest.raises(OSError):
        execute(rig)
    before = rig.boundary.calls[:]
    second = provision.Provisioner(rig.lease, rig.transport,
        register_staging=rig.registered.append, boundary=rig.boundary,
        input_reader=rig.reader)
    rig.boundary.fail = rig.boundary.lost_reply = None
    with pytest.raises(ValueError):
        second.provision(rig.selection, ['mechanical'], attempt_id=rig.attempt)
    assert rig.boundary.calls == before
    rig.lease.restore.assert_not_called()


def test_other_provisioner_cannot_leave_old_readiness_authoritative(rig):
    ready = execute(rig)
    before = rig.boundary.calls[:]
    second = provision.Provisioner(rig.lease, rig.transport,
        register_staging=rig.registered.append, boundary=rig.boundary,
        input_reader=rig.reader)
    with pytest.raises(ValueError):
        second.provision(rig.selection, ['trusted-hard'], attempt_id=rig.attempt)
    assert rig.boundary.calls == before
    with pytest.raises(ValueError):
        rig.control.require_ready(ready)


def test_recorded_restore_starts_fresh_generation_without_reviving_old_receipts(rig, tmp_path):
    ready = execute(rig)
    rig.lease.state['phase'] = 'complete'
    rig.lease.state['domain_id'] = None
    rig.lease.view = SimpleNamespace(domain_id=None, snapshot=Mock(return_value=('recorded', True)))
    provision.reset_after_restore(rig.lease)
    rig.lease.guard.assert_any_call(off=True)
    with pytest.raises(ValueError):
        rig.control.require_ready(ready)
    rig.lease.state.update(phase='running', domain_id=71)
    rig.transport.call.return_value = ('f' * 64 + '\n').encode()
    boundary = FilesystemBoundary(tmp_path / 'restored-guest', rig.registered,
                                  rig.input['manifest']['inputs']['target'])
    boundary.input = rig.input
    fresh = provision.Provisioner(rig.lease, rig.transport,
        register_staging=rig.registered.append, boundary=boundary, input_reader=rig.reader)
    newer = fresh.provision(rig.selection, ['mechanical'], attempt_id='fresh-restored-attempt')
    assert fresh.require_ready(newer) == newer
    assert newer.binding['boot_sha256'] != ready.binding['boot_sha256']
    with pytest.raises(ValueError):
        rig.control.require_ready(newer)


@pytest.mark.parametrize('fault', ['running', 'boot', 'held-lease', 'active-domain',
                                  'snapshot', 'ownership', 'unrestored-suite'])
def test_generation_reset_requires_existing_owner_recorded_off_restore(rig, fault):
    rig.boundary.lost_reply = 'stage'
    with pytest.raises(OSError):
        execute(rig)
    rig.lease.state.update(phase='complete', domain_id=None)
    rig.lease.view = SimpleNamespace(domain_id=None, snapshot=Mock(return_value=('recorded', True)))
    if fault == 'running':
        rig.lease.state.update(phase='running', domain_id=71)
    elif fault == 'boot':
        rig.transport.call.return_value = ('f' * 64 + '\n').encode()
        rig.lease.state.update(phase='running', domain_id=71)
    elif fault == 'held-lease':
        rig.lease.fd = None
    elif fault == 'active-domain':
        rig.lease.view.domain_id = 71
    elif fault == 'snapshot':
        rig.lease.view.snapshot.return_value = ('recorded', False)
    elif fault == 'ownership':
        rig.lease.guard.side_effect = ValueError('foreign lease owner')
    else:
        rig.lease.state.update(phase='isolated')
        rig.lease._restored = False
    before = rig.boundary.calls[:]
    with pytest.raises(ValueError):
        provision.reset_after_restore(rig.lease)
    assert rig.control.failed and rig.boundary.calls == before


def test_authenticated_bundle_reads_real_frozen_input_without_changing_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    source = {name: b'# source ' + name.encode() for name in artifact_inputs.NATIVE_RUNTIME_SOURCES}
    inputs = {'source': {name: {'sha256': sha(data), 'length': len(data), 'mode': 0o644}
                         for name, data in source.items()},
              'toolchain': {'environment': environment_record('ubuntu'),
                            'compiler': compiler_record('ubuntu')},
              'target': {'os': 'ubuntu', 'release': '26.04', 'architecture': 'x86_64'},
              'dependencies': fixture_manifest.DEPENDENCIES}
    payloads = {}
    for key, member in fixture_manifest.declarations().items():
        value = member['source']
        if type(value) is bytes:
            payloads[key] = value
        elif value in ('onpc-test-gui.py', 'gtk_automation.py'):
            name = ('tests/fixtures/gui_application.py' if value == 'onpc-test-gui.py'
                    else 'common/oh_no_parent_control_ui/gtk_automation.py')
            payloads[key] = source[name]
        else:
            payloads[key] = inert_elf(value)
    store = retention.Store(storage.directory('state') / 'retention-provision-test')
    with store.session():
        key = fixture_execution.input_key(inputs['source'], inputs['toolchain']['environment'], 'ubuntu')
        allocation = Path(retention.allocate(tempfile.mkdtemp,
            prefix=fixture_execution._prefix('ubuntu', key), dir=str(storage.allocation_parent())))
        bundle = allocation / 'native-runtime'
        bundle.mkdir(mode=0o700)
        manifest = fixture_manifest.write(bundle, inputs, payloads)
        with store.opened() as fd:
            state, info = store.read(fd), os.fstat(fd)
        allocated = allocation.stat()
        selection = fixture_execution.Selection('ubuntu', key, str(allocation),
            allocated.st_dev, allocated.st_ino, str(store.path), info.st_dev, info.st_ino,
            state['run'], manifest['build_identity'])
        with store.opened() as fd:
            before = copy.deepcopy(store.read(fd))
        loaded = provision.authenticated_bundle(selection)
        assert loaded['manifest'] == fixture_execution.verify(selection)
        assert set(loaded['payloads']) == set(loaded['manifest']['members'])
        for key, payload in loaded['payloads'].items():
            member = loaded['manifest']['members'][key]
            assert len(payload) == member['length'] and sha(payload) == member['sha256']
        raw = (selection.path / 'fixture-manifest.json').read_bytes()
        archive = (selection.path / 'payload.tar').read_bytes()
        assert loaded['content_identity'] == sha(raw + archive)
        with store.opened() as fd:
            assert store.read(fd) == before
        (selection.path / 'payload.tar').write_bytes(b'changed-after-selection')
        with pytest.raises(ValueError):
            provision.authenticated_bundle(selection)


@pytest.fixture
def real_guest(rig, tmp_path):
    execute(rig, ('activity', 'mechanical', 'native', 'trusted-hard'))
    request = next(copy.deepcopy(request) for action, request in rig.boundary.calls
                   if action == 'preflight')
    root = tmp_path / 'real-guest'
    root.mkdir(mode=0o700)
    (root / 'run').mkdir(mode=0o755)
    files = guest.Files(root, uid_map=lambda _: os.getuid(), gid_map=lambda _: os.getgid())
    native, witness = Mock(), Mock()
    boundary = guest.Guest(files, native, request['accounts'], witness, target=request['target'])
    return SimpleNamespace(root=root, files=files, native=native, witness=witness,
                           boundary=boundary, request=request,
                           payloads={key: rig.input['payloads'][key] for key in request['members']})


def guest_stage(real):
    assert real.boundary.call('preflight', real.request) == {'ok': True}
    reserved = real.boundary.call('reserve', real.request)
    assert reserved['ok'] is True
    real.request['stage_identity'] = reserved['identity']
    staged = real.boundary.call('stage', real.request, real.payloads)
    assert staged['ok'] is True
    real.request['stage_files'] = staged['identities']


def test_real_guest_places_exact_selected_bytes_modes_and_cleans_owned_stage(real_guest):
    r = real_guest
    guest_stage(r)
    r.boundary.call('place', r.request)
    r.boundary.call('activate', r.request)
    observed = r.boundary.call('readback', r.request)
    assert observed == {'files': {key: {name: item[name] for name in
        ('sha256', 'length', 'mode', 'uid', 'gid')} for key, item in r.request['members'].items()},
        'native': True, 'labels': True}
    assert r.boundary.call('witness', r.request) == {'ready': True}
    r.witness.assert_called_once_with(r.request)
    r.native.activate.assert_called_once_with(r.request)
    r.native.verify.assert_called_once_with(r.request)
    for key, item in r.request['members'].items():
        path = r.root / item['destination'].lstrip('/')
        assert path.read_bytes() == r.payloads[key]
        assert path.stat().st_mode & 0o777 == item['mode']
    r.boundary.call('clean', r.request)
    assert not (r.root / r.request['staging'].lstrip('/')).exists()
    repeat = {**r.request, 'repeat': True}
    r.boundary.call('preflight', repeat)
    r.boundary.call('readback', repeat)
    with pytest.raises(ValueError):
        r.boundary.call('place', repeat)


@pytest.mark.parametrize('fault', ['unknown', 'modified', 'file-link', 'hardlink',
                                  'fifo', 'directory', 'mode', 'owner', 'unsafe-parent', 'parent-link'])
def test_real_guest_refuses_foreign_modified_and_unsafe_paths_without_mutation(real_guest, fault):
    r = real_guest
    for member_key, member in r.request['members'].items():
        r.files.write(member['destination'], r.payloads[member_key],
                      uid=member['uid'], gid=member['gid'], mode=member['mode'])
    key, item = next((key, item) for key, item in r.request['members'].items()
                     if fault != 'owner' or item['owner'] == 'other')
    path = r.root / item['destination'].lstrip('/')
    if fault == 'file-link':
        path.unlink()
        path.symlink_to(path.parent / 'absent')
    elif fault == 'hardlink':
        path.write_bytes(r.payloads[key])
        os.link(path, path.parent / 'other-link')
    elif fault == 'fifo':
        path.unlink()
        os.mkfifo(path)
    elif fault == 'directory':
        path.unlink()
        path.mkdir()
    else:
        path.write_bytes(b'foreign' if fault in ('unknown', 'modified') else r.payloads[key])
        path.chmod(item['mode'])
    if fault == 'mode':
        path.chmod(0o666)
    elif fault == 'owner':
        r.files.uid_map = lambda uid: os.getuid() + 1 if uid == item['uid'] else os.getuid()
    elif fault == 'unsafe-parent':
        path.parent.chmod(0o777)
    elif fault == 'parent-link':
        path.unlink()
        displaced = path.parent.with_name(path.parent.name + '-original')
        path.parent.rename(displaced)
        path.parent.symlink_to(displaced, target_is_directory=True)
    request = {**r.request, 'repeat': fault != 'unknown'}
    with pytest.raises((ValueError, OSError)):
        r.boundary.call('preflight', request)
    r.native.activate.assert_not_called()
    r.witness.assert_not_called()
    assert not (r.root / r.request['staging'].lstrip('/')).exists()


@pytest.mark.parametrize('fault', ['missing', 'extra', 'changed'])
def test_real_guest_checks_complete_staged_payload_before_first_placement(real_guest, fault):
    r = real_guest
    guest_stage(r)
    key = next(iter(r.payloads))
    stage = r.root / r.request['staging'].lstrip('/')
    if fault == 'missing':
        (stage / key).unlink()
    elif fault == 'changed':
        (stage / key).write_bytes(b'changed staging')
    else:
        # An undeclared input must be refused before writing the declared ones.
        payloads = r.payloads | {'unknown-member': b'not selected'}
        with pytest.raises(ValueError, match='payload-membership'):
            r.boundary.call('stage', r.request, payloads)
        return
    with pytest.raises((ValueError, OSError)):
        r.boundary.call('place', r.request)
    assert not any((r.root / item['destination'].lstrip('/')).exists()
                   for item in r.request['members'].values())


def test_real_guest_cleanup_preserves_replaced_stage_and_diagnostics(real_guest):
    r = real_guest
    guest_stage(r)
    stage = r.root / r.request['staging'].lstrip('/')
    (stage / 'unexpected-diagnostic').write_bytes(b'preserve this diagnostic')
    before = {p.name: p.read_bytes() for p in stage.iterdir()}
    with pytest.raises(ValueError, match='staging-inventory'):
        r.boundary.call('clean', r.request)
    assert {p.name: p.read_bytes() for p in stage.iterdir()} == before


@pytest.mark.parametrize('replace', ['directory', 'member'])
def test_real_guest_cleanup_refuses_matching_metadata_replacements(real_guest, replace):
    r = real_guest
    guest_stage(r)
    stage = r.root / r.request['staging'].lstrip('/')
    if replace == 'directory':
        original = stage.with_name(stage.name + '-original')
        stage.rename(original)
        stage.mkdir(mode=0o700)
        for key, payload in r.payloads.items():
            (stage / key).write_bytes(payload)
            (stage / key).chmod(0o600)
    else:
        key = next(iter(r.payloads))
        (stage / key).rename(stage.parent / 'preserved-original-member')
        (stage / key).write_bytes(r.payloads[key])
        (stage / key).chmod(0o600)
    before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in stage.iterdir()}
    with pytest.raises(ValueError):
        r.boundary.call('clean', r.request)
    assert {p.name: (p.stat().st_ino, p.read_bytes()) for p in stage.iterdir()} == before


def test_real_file_creation_uses_primary_gid_independent_of_uid(tmp_path):
    gids = []
    def group(gid):
        gids.append(gid)
        return os.getgid()
    files = guest.Files(tmp_path, uid_map=lambda _: os.getuid(), gid_map=group)
    files.write('/home/child/private/fixture', b'exact bytes', uid=1001, gid=2001)
    assert 2001 in gids and 1001 not in gids


class NativeCommands:
    """Public native CLI double; only its exact add/update actions mutate trust."""
    def __init__(self, files, request):
        self.files, self.request, self.calls = files, request, []
        self.installed, self.extra_rows = False, []
        self.tool_bytes = {}

    def __call__(self, argv):
        self.calls.append(argv)
        if argv[0] == '/usr/bin/systemctl':
            return b'MainPID=123\nInvocationID=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nActiveState=active\n'
        if argv[0] == '/usr/bin/journalctl':
            row = lambda message, cursor: {'_PID': '123',
                '_SYSTEMD_INVOCATION_ID': 'a' * 32, 'MESSAGE': message, '__CURSOR': cursor}
            rows = [] if '--after-cursor' in argv else [row('Starting to listen for events', 'start')]
            if self.installed:
                rows.append(row('Updated', 'updated'))
            return b''.join(json.dumps(item).encode() + b'\n' for item in rows)
        if argv[:2] == ['dpkg-query', '-S']:
            return ('fapolicyd: ' + argv[2] + '\n').encode()
        if argv[:2] == ['dpkg-query', '-W']:
            return b'fapolicyd 1.0\n'
        if argv == ['dpkg-query', '--control-show', 'fapolicyd', 'md5sums']:
            return ''.join(hashlib.md5(data).hexdigest() + '  ' + path.lstrip('/') + '\n'
                           for path, data in self.tool_bytes.items()).encode()
        if argv[1:3] == ['--file', 'add']:
            assert argv[4:] == ['--trust-file', Path(guest.TRUST).name]
            item = next(item for item in self.request['members'].values()
                        if item['destination'] == argv[3])
            path = self.files.root / guest.TRUST.lstrip('/')
            with path.open('ab') as stream:
                stream.write(f"{argv[3]} {item['length']} {item['sha256']}\n".encode())
        if argv[1:] == ['--update']:
            self.installed = True
        if argv[1:] == ['--dump-db']:
            rows = self.extra_rows[:]
            if self.installed:
                rows += [f"filedb {m['destination']} {m['length']} {m['sha256']}"
                         for m in self.request['members'].values() if m['native_action'] == 'trust']
            return ('\n'.join(rows) + '\n').encode()
        if argv == ['/usr/sbin/fagenrules', '--check']:
            return b'/usr/sbin/fagenrules: No change\n'
        return b''


@pytest.fixture
def real_native(real_guest):
    r = real_guest
    f = r.files
    backend = b'trust = debdb,file\n'
    record = {'purpose': native_trust.BACKEND_PURPOSE, 'os_id': 'ubuntu',
              'before_hex': backend.hex(), 'after_hex': backend.hex(),
              'metadata': {'mode': 0o644, 'uid': 0, 'gid': 0}, 'complete': True}
    f.write(native_trust.BACKEND_RECORD, json.dumps(record).encode(), mode=0o600)
    f.write(native_trust.BACKEND_CONFIG, backend, mode=0o644)
    with f.directory('/etc/fapolicyd/trust.d', create=True):
        pass
    f.write('/etc/fapolicyd/trust.d/vendor.trust', b'# preserve vendor trust\n', mode=0o600)
    commands = NativeCommands(f, r.request)
    commands.tool_bytes = {path: ('inert-native-tool ' + path).encode()
                          for path in native_trust.native_tool_paths('ubuntu').values()}
    for path, data in commands.tool_bytes.items():
        f.write(path, data, mode=0o755)
    native = guest.Native(f, commands, r.request['target'], service_gid=1234)
    return SimpleNamespace(**vars(r), commands=commands, native_api=native)


def test_real_native_uses_exact_public_trust_actions_and_preserves_environment(real_native):
    r = real_native
    original = r.files.read(native_trust.BACKEND_CONFIG)
    r.native_api.preflight(r.request)
    r.native_api.activate(r.request)
    r.native_api.verify(r.request)
    trusted = {item['destination'] for item in r.request['members'].values()
               if item['native_action'] == 'trust'}
    adds = [argv for argv in r.commands.calls if argv[1:3] == ['--file', 'add']]
    assert [argv[3] for argv in adds] == sorted(trusted)
    assert len([argv for argv in r.commands.calls if argv[1:] == ['--update']]) == 1
    assert r.files.read(native_trust.BACKEND_CONFIG) == original
    assert r.files.read('/etc/fapolicyd/trust.d/vendor.trust', mode=0o600) == b'# preserve vendor trust\n'
    assert not any('rule' in ' '.join(argv) for argv in r.commands.calls)
    before = r.commands.calls[:]
    r.native_api.preflight({**r.request, 'repeat': True})
    assert [argv for argv in r.commands.calls[len(before):]
            if argv[1:3] == ['--file', 'add'] or argv[1:] == ['--update']] == []


def test_native_database_mismatch_retains_exact_fixture_diagnostic(real_native):
    r = real_native
    key, member = next((key, item) for key, item in r.request['members'].items()
                       if item['native_action'] == 'trust')
    request = {**r.request, 'members': {key: member}}
    with pytest.raises(ValueError, match='native-database:') as failure:
        r.native_api.verify_database(request)
    diagnostic = json.loads(str(failure.value).split('native-database:', 1)[1])
    assert diagnostic == {'member': key, 'observed': [],
        'expected': [['filedb', str(member['length']), member['sha256']]]}
    assert r.commands.calls == [[r.native_api.cli, '--dump-db']]


def test_native_activation_observes_completion_before_dump_without_repeating_update(real_native, monkeypatch):
    r = real_native
    clock, observations, reads = [0.0], [], []
    original = r.native_api.command

    def command(argv):
        if argv[0] == '/usr/bin/journalctl' and '--after-cursor' in argv:
            observations.append(clock[0])
            if len(observations) <= 2:
                r.commands.calls.append(argv)
                return b''
        if argv == [r.native_api.cli, '--dump-db']:
            reads.append(clock[0])
        return original(argv)

    monkeypatch.setattr(guest.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(guest.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    r.native_api.command = command
    r.native_api.activate(r.request)
    assert observations == [0.0, 0.2, 0.4]
    assert reads == [0.4]
    assert sum(argv[1:] == ['--update'] for argv in r.commands.calls) == 1


def test_native_startup_observation_precedes_any_database_access(real_native, monkeypatch):
    r = real_native
    clock, observations = [0.0], []
    original = r.native_api.command

    def command(argv):
        if argv[0] == '/usr/bin/journalctl':
            observations.append(clock[0])
            if len(observations) <= 2:
                r.commands.calls.append(argv)
                return b''
        return original(argv)

    monkeypatch.setattr(guest.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(guest.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    r.native_api.command = command
    r.native_api.ready()
    assert observations == [0.0, 0.2, 0.4]
    assert not r.files.exists(guest.TRUST)
    assert not any(argv[1:] in (['--dump-db'], ['--update']) for argv in r.commands.calls)


@pytest.mark.parametrize('fault', ['restart', 'foreign-record', 'old-completion', 'command-error'])
def test_native_event_wait_never_adopts_foreign_or_uncertain_observations(real_native, monkeypatch, fault):
    r = real_native
    identity = r.native_api._service()
    service = Mock(return_value=identity)
    journal = Mock(return_value=[])
    monkeypatch.setattr(r.native_api, '_service', service)
    monkeypatch.setattr(r.native_api, '_journal', journal)
    if fault == 'restart':
        service.side_effect = [identity, {**identity, 'InvocationID': 'b' * 32}]
    elif fault == 'command-error':
        journal.side_effect = OSError('read failed')
    elif fault == 'foreign-record':
        # Exercise the real journal parser's invocation pin independently.
        monkeypatch.setattr(r.native_api, 'command', Mock(return_value=json.dumps({
            '_PID': identity['MainPID'], '_SYSTEMD_INVOCATION_ID': 'b' * 32,
            'MESSAGE': 'Updated', '__CURSOR': 'foreign'}).encode()))
        with pytest.raises(ValueError, match='native-journal-identity'):
            guest.Native._journal(r.native_api, identity)
        return
    else:
        # The cursor is required for update observation, so old completions
        # cannot be used. Simulate no post-cursor response until the deadline.
        monkeypatch.setattr(guest.time, 'monotonic', Mock(side_effect=[0.0, 180.0]))
    with pytest.raises((ValueError, OSError)):
        r.native_api._event('Updated', identity, after='current-cursor')
    journal.assert_called_once_with(identity, after='current-cursor')
    assert not any(argv[1:] == ['--update'] for argv in r.commands.calls)


def test_native_activation_missing_completion_times_out_without_second_update_or_dump(real_native, monkeypatch):
    r = real_native
    clock = [0.0]
    original = r.native_api.command

    def command(argv):
        if argv[0] == '/usr/bin/journalctl' and '--after-cursor' in argv:
            r.commands.calls.append(argv)
            return b''
        return original(argv)

    monkeypatch.setattr(guest.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(guest.time, 'sleep', lambda seconds: clock.__setitem__(0, 180.0))
    r.native_api.command = command
    with pytest.raises(ValueError, match='native-event-timeout:Updated'):
        r.native_api.activate(r.request)
    assert not any(argv[1:] == ['--dump-db'] for argv in r.commands.calls)
    assert sum(argv[1:] == ['--update'] for argv in r.commands.calls) == 1


@pytest.mark.parametrize('fault', ['conflict', 'duplicate', 'control'])
def test_native_activation_refuses_unsafe_rows_immediately(real_native, monkeypatch, fault):
    r = real_native
    trusted = next(m for m in r.request['members'].values() if m['native_action'] == 'trust')
    row = f"filedb {trusted['destination']} {trusted['length']} {trusted['sha256']}"
    if fault == 'conflict':
        row = row.replace(trusted['sha256'], '0' * 64)
    elif fault == 'control':
        control = next(m for m in r.request['members'].values() if m['native_action'] != 'trust')
        row = f"filedb {control['destination']} {control['length']} {control['sha256']}"
    r.commands.extra_rows = [row]
    monkeypatch.setattr(guest.time, 'sleep', Mock(side_effect=AssertionError('must not wait on unsafe rows')))
    with pytest.raises(ValueError, match='native-database:'):
        r.native_api.activate(r.request)
    assert sum(argv[1:] == ['--dump-db'] for argv in r.commands.calls) == 1
    assert sum(argv[1:] == ['--update'] for argv in r.commands.calls) == 1


@pytest.mark.parametrize('fault', ['backend', 'pending', 'foreign-trust', 'database-trust', 'tool'])
def test_real_native_refuses_stale_or_foreign_provenance_before_native_writes(real_native, fault):
    r = real_native
    item = next(iter(r.request['members'].values()))
    if fault == 'backend':
        (r.root / native_trust.BACKEND_CONFIG.lstrip('/')).write_bytes(b'trust = debdb\n')
    elif fault == 'pending':
        r.files.write(native_trust.BACKEND_PENDING, b'pending', mode=0o600)
    elif fault == 'foreign-trust':
        r.files.write('/etc/fapolicyd/trust.d/foreign.trust',
            f"{item['destination']} {item['length']} {item['sha256']}\n".encode(), mode=0o600)
    elif fault == 'database-trust':
        r.commands.extra_rows = [f"filedb {item['destination']} {item['length']} {item['sha256']}"]
    else:
        (r.root / r.native_api.cli.lstrip('/')).write_bytes(b'altered native executable')
    with pytest.raises(ValueError):
        r.native_api.preflight(r.request)
    assert not r.files.exists(guest.TRUST)
    assert not any(argv[1:3] == ['--file', 'add'] or argv[1:] == ['--update']
                   for argv in r.commands.calls)
    if fault == 'tool':
        assert not any(argv[0] == r.native_api.cli for argv in r.commands.calls)


def test_fedora_labels_and_admissions_are_exact_selected_contents(real_native):
    r = real_native
    native = guest.Native(r.files, r.commands,
        {'os': 'fedora', 'release': '44', 'architecture': 'x86_64'}, service_gid=1234)
    rules = native._rules(r.request)
    assert set(rules) == set(native_assets.NATIVE_POLICY_PATHS)
    assert all(b'trust=0' in data and b'dir=' not in data for data in rules.values())
    native.labels(r.request)
    native.labels(r.request, verify=True)
    expected = sorted([item['destination'] for item in r.request['members'].values()]
                      + list(rules) + [guest.TRUST])
    assert r.commands.calls == [
        ['/usr/sbin/restorecon', '-F', '--', path] for path in expected] + [
        ['/usr/sbin/matchpathcon', '-V', path] for path in expected]


@pytest.mark.parametrize('fault', [None, 'mode', 'symlink', 'directory', 'header'])
def test_real_fedora_stock_preserves_generated_product_layer_observed_group(real_native, monkeypatch, fault):
    r = real_native
    samples = {'/usr/share/fapolicyd/default-ruleset.known-libs':
               ('\n'.join(native_assets.NATIVE_STOCK_RULE_NAMES) + '\n').encode()}
    for index, name in enumerate(native_assets.NATIVE_STOCK_RULE_NAMES):
        samples['/usr/share/fapolicyd/sample-rules/' + name] = (
            f'# vendor stock {index}\n').encode()
    rows = []
    for path, data in samples.items():
        r.files.write(path, data)
        rows.append(f'{path}\t{sha(data)}\t{stat.S_IFREG | 0o644}\troot\troot\t0\n')
    for name in native_assets.NATIVE_STOCK_RULE_NAMES:
        r.files.write('/etc/fapolicyd/rules.d/' + name,
                      samples['/usr/share/fapolicyd/sample-rules/' + name])
    product = '/etc/fapolicyd/rules.d/01-oh-no-parent-control-deny.rules'
    r.files.write(product, b'# Generated by Oh No! Parent Control. Do not edit.\n# owned policy\n')
    path = r.root / product.lstrip('/')
    if fault == 'mode':
        path.chmod(0o666)
    elif fault == 'symlink':
        path.unlink()
        path.symlink_to(path.parent / native_assets.NATIVE_STOCK_RULE_NAMES[0])
    elif fault == 'directory':
        path.unlink()
        path.mkdir()
    elif fault == 'header':
        path.write_bytes(b'# unrelated foreign policy\n')
    native = guest.Native(r.files, Mock(return_value=''.join(rows).encode()),
        {'os': 'fedora', 'release': '44', 'architecture': 'x86_64'},
        service_gid=os.getgid() + 99)
    read = Mock(wraps=r.files.read)
    monkeypatch.setattr(r.files, 'read', read)
    if fault:
        with pytest.raises((ValueError, OSError)):
            native._stock({})
    else:
        before = path.read_bytes(), path.stat()
        native._stock({})
        assert (path.read_bytes(), path.stat()) == before
        product_reads = [call for call in read.call_args_list if call.args[0] == product]
        assert len(product_reads) == 1
        assert product_reads[0].kwargs['gid'] == path.stat().st_gid


def test_ssh_wire_embedded_modules_execute_only_over_private_guest(real_guest, tmp_path, monkeypatch):
    r = real_guest
    transport = Mock()
    transport.call.return_value = b'{"ok":true}'
    assert provision.SSHBoundary(transport).call('stage', r.request, r.payloads) == {'ok': True}
    transport.call.assert_called_once()
    sent = transport.call.call_args
    assert sent.args[0][:3] == ['/usr/bin/python3', '-I', '-c']
    assert sent.kwargs['attempts'] == 1 and sent.kwargs['timeout'] == 300
    wire = json.loads(sent.kwargs['input'])
    assert wire['action'] == 'stage' and wire['request'] == r.request
    payloads = {key: base64.b64decode(value, validate=True)
                for key, value in wire['payloads'].items()}
    assert payloads == r.payloads
    assert {name for name, _ in wire['modules']} == {
        'guest_files', 'native_assets', 'baseline_assets', 'native_trust',
        'fixture_manifest', 'fixture_process', 'fixture_guest'}
    shipped = {}
    original_import = builtins.__import__

    def guest_import(name, *args, **kwargs):
        assert name.split('.')[0] not in ('tests', 'tools'), 'checkout import in guest payload'
        return original_import(name, *args, **kwargs)

    # The real guest has no checkout package. Do not let this pytest process's
    # imports conceal a missing dependency in the transferred module closure.
    with monkeypatch.context() as isolated:
        isolated.setattr(builtins, '__import__', guest_import)
        for name, source in wire['modules']:
            module = ModuleType(name)
            monkeypatch.setitem(sys.modules, name, module)
            exec(compile(source, '<shipped-' + name + '>', 'exec'), module.__dict__)
            shipped[name] = module
    assert shipped['fixture_manifest'].declarations() == fixture_manifest.declarations()
    assert callable(shipped['fixture_process'].launch_native)
    assert callable(shipped['fixture_process'].terminate)
    root = tmp_path / 'wire-guest'
    root.mkdir(mode=0o700)
    (root / 'run').mkdir(mode=0o755)
    module = shipped['fixture_guest']
    files = module.Files(root, uid_map=lambda _: os.getuid(), gid_map=lambda _: os.getgid())
    # The production default_guest entry point is never called on this host.
    boundary = module.Guest(files, Mock(), r.request['accounts'], Mock(), target=r.request['target'])
    private = SimpleNamespace(boundary=boundary, request=copy.deepcopy(r.request), payloads=payloads)
    guest_stage(private)
    boundary.call('place', private.request)
    observed = boundary.call('readback', private.request)
    assert set(observed['files']) == set(payloads)
    boundary.call('clean', private.request)
    assert not (root / private.request['staging'].lstrip('/')).exists()


def test_ssh_lost_reply_is_never_retried(real_guest):
    transport = Mock()
    transport.call.side_effect = TimeoutError('uncertain private SSH reply')
    with pytest.raises(TimeoutError):
        provision.SSHBoundary(transport).call('stage', real_guest.request, real_guest.payloads)
    transport.call.assert_called_once()
    assert transport.call.call_args.kwargs['attempts'] == 1


def test_ready_input_is_refused_during_shared_transaction_without_transport(rig):
    ready = execute(rig)
    count, calls = rig.transport.call.call_count, rig.boundary.calls[:]
    scenario_input = Mock()
    with rig.control._shared['lock']:
        with pytest.raises(ValueError):
            rig.control.require_ready(ready)
            scenario_input()
    scenario_input.assert_not_called()
    assert rig.transport.call.call_count == count
    assert rig.boundary.calls == calls and rig.control.failed
    fresh = provision.Provisioner(rig.lease, rig.transport,
        register_staging=rig.registered.append, boundary=rig.boundary, input_reader=rig.reader)
    with pytest.raises(ValueError):
        fresh.provision(rig.selection, ['mechanical'], attempt_id=rig.attempt)
    assert rig.transport.call.call_count == count and rig.boundary.calls == calls
