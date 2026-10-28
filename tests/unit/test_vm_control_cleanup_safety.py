"""VM maintenance uses real lease files/locks with exclusively mocked VM calls."""
from tests.support.vm_registry import vm_name
import json
import hashlib
from pathlib import Path
import runpy
import os
import time
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import system_runner as runner
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig, UUID

import vm_control as control

VM_ARGS = ['--vm', vm_name()]


@pytest.mark.parametrize(('target', 'authenticated'),
                         [('ubuntu', True), ('fedora', True), ('fedora', False)])
def test_fixture_sync_dispatch_authenticates_before_resuming_owned_maintenance(
        monkeypatch, tmp_path, target, authenticated):
    import fixture_maintenance as maintenance
    from tools import fixture_execution, fixture_provision, test_storage
    selection = {'target': target}
    monkeypatch.setattr(fixture_execution.Selection, 'from_record',
                        lambda value: SimpleNamespace(record=lambda: value))
    authenticate = Mock(side_effect=None if authenticated else runner.Error('fixture:input-refused'))
    monkeypatch.setattr(fixture_provision, 'authenticated_bundle', authenticate)
    api, source, lease, commands = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(control.importlib, 'import_module', lambda name: api)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.os, 'getegid', lambda: 0)
    monkeypatch.setattr(control.os, 'umask', Mock())
    monkeypatch.setattr(control.threading, 'Thread', Mock())
    monkeypatch.setattr(control.runner.baseline, 'LibvirtSource', lambda value: source)
    monkeypatch.setattr(control.runner, 'Commands', lambda: commands)
    monkeypatch.setattr(control.runner, 'Lease', lambda *args, **kwargs: lease)
    monkeypatch.setattr(test_storage, 'scratch_directory', lambda: tmp_path)
    monkeypatch.setattr(control.tempfile, 'mkdtemp', lambda **kwargs: str(tmp_path))
    monkeypatch.setattr(control, 'check_identity', Mock())
    resume = Mock()
    monkeypatch.setattr(control, 'resume', resume)
    synchronize = Mock(return_value=SimpleNamespace(binding={'ready': target}))
    monkeypatch.setattr(maintenance, 'synchronize', synchronize)
    assert control.main([*VM_ARGS, '--expected-uuid', UUID, 'sync-fixtures',
                         '--fixture-selection', json.dumps(selection)]) == (0 if authenticated else 2)
    authenticate.assert_called_once_with(selection)
    if authenticated:
        resume.assert_called_once_with(lease, fixture_maintenance=True)
        synchronize.assert_called_once_with(lease, selection)
        lease.release.assert_called_once_with()
        source.close.assert_called_once_with()
    else:
        api.virEventRegisterDefaultImpl.assert_not_called()
        resume.assert_not_called()
        synchronize.assert_not_called()


@pytest.mark.parametrize('extra', [None, 'desktop', 'tty', 'user-manager', 'other-ssh', 'unknown'])
def test_idle_maintenance_session_boundary_accepts_only_owned_background_sessions(extra):
    from fixture_maintenance import idle_sessions
    ssh = {'Class': 'user', 'Type': 'tty', 'Service': 'sshd', 'User': '0', 'Remote': 'yes'}
    greeter = {'Class': 'greeter', 'Type': 'wayland', 'Service': 'gdm-launch-environment',
               'User': '120', 'Remote': 'no'}
    manager = {'Class': 'manager-early', 'Type': 'unspecified', 'Service': 'systemd-user',
               'User': '0', 'Remote': 'no'}
    sessions = [('own', ssh), ('greeter', greeter), ('root-manager', manager),
                ('greeter-manager', dict(manager, User='120'))]
    if extra is not None:
        props = {'desktop': dict(greeter, Class='user', Service='gdm-password', User='1001'),
                 'tty': dict(ssh, User='1001'),
                 'user-manager': dict(manager, User='1001'),
                 'other-ssh': dict(ssh), 'unknown': {}}[extra]
        sessions.append(('foreign', props))
    assert idle_sessions(sessions, 'own') is (extra is None)
    assert idle_sessions(sessions, 'own', allow_prior_ssh=True) is (extra in (None, 'other-ssh'))
    assert idle_sessions(sessions, None) is False
    sessions[0] = ('own', dict(ssh, Class='unknown'))
    assert idle_sessions(sessions, 'own', allow_prior_ssh=True) is False


@pytest.mark.parametrize('fault', [None, 'owned-start', 'foreign-start', 'report-write', 'report-close'])
def test_fixture_qualification_starts_watch_before_report_owner(tmp_path, monkeypatch, fault):
    from contextlib import contextmanager, nullcontext
    import fixture_live_refresh_qualification as qualification
    from tools import test_storage
    active = []
    events = []
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    state = tmp_path / 'state'
    state.mkdir()
    selected = SimpleNamespace(target='ubuntu', record=lambda: {'selected': 'A'})
    monkeypatch.setattr(qualification, 'selected_target', lambda: 'ubuntu')
    actual_require = qualification.require
    monkeypatch.setattr(qualification, 'require', lambda value, reason:
        None if reason == 'root-required' else actual_require(value, reason))
    monkeypatch.setattr(qualification.os, 'umask', lambda mode: 0o022)
    monkeypatch.setattr(qualification.fixture_execution.Selection, 'from_record', lambda value: selected)
    monkeypatch.setattr(qualification.fixture_execution, 'validate_source_selection', lambda value, selection: value)
    monkeypatch.setattr(qualification.fixture_execution, 'verify', lambda value: {})
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', lambda value: {})
    monkeypatch.setattr(qualification, 'authenticated_input', lambda value: nullcontext(12))
    monkeypatch.setattr(test_storage, 'scratch_directory', lambda: scratch)
    source = Mock()
    monkeypatch.setattr(qualification, 'open_source', lambda: (source, Mock()))
    leases = []
    def lease_factory(source, commands, inspect, **kwargs):
        lease = SimpleNamespace(commands=commands, directory=state, fd=None, state=None,
            original_id=None, ownership_run=None, release=Mock())
        leases.append(lease)
        return lease
    monkeypatch.setattr(qualification.system, 'Lease', lease_factory)
    @contextmanager
    def report():
        events.append('report-open')
        active.append(True)
        try:
            yield
        finally:
            active.pop()
            events.append('report-close')
        if fault == 'report-close' and events.count('report-close') == 1:
            raise ValueError('simulated report closure failure')
    monkeypatch.setattr(qualification, 'recovery_session', report)
    monkeypatch.setattr(qualification, 'allocate', lambda factory, **kwargs: factory(dir=tmp_path, **kwargs))
    def operate(lease, action, keys, **kwargs):
        events.append(action)
        assert not active  # A keeper must not inherit a phase report owner.
        if action == 'start':
            assert kwargs == {'fixture_maintenance': True}
            if fault != 'foreign-start':
                lease.fd, lease.original_id, lease.ownership_run = 17, -1, 'owned-run'
                lease.state = {'phase': 'running', 'run': 'owned-run'}
            if fault in ('owned-start', 'foreign-start'):
                raise ValueError('simulated startup refusal')
        else:
            assert action == 'stop' and len(leases) == 2
            lease.state = {'phase': 'complete'}
    monkeypatch.setattr(qualification.control, 'operate', operate)
    def use(*args):
        assert active and events == ['start', 'report-open']
        return {'outcome': 'passed'}
    monkeypatch.setattr(qualification, 'retain_a', use)
    original_encode = qualification.system.baseline.encode
    def encode(value):
        if fault == 'report-write' and value == {'outcome': 'passed'}:
            raise OSError('simulated result write failure')
        return original_encode(value)
    monkeypatch.setattr(qualification.system.baseline, 'encode', encode)
    assert qualification.main(phase='retain-a', selection={}, source_selection={}) == (1 if fault else 0)
    assert events[0] == 'start'
    assert events.count('stop') == (1 if fault in ('owned-start', 'report-write', 'report-close') else 0)
    if fault == 'owned-start':
        assert events.index('stop') < events.index('report-open')
    source.close.assert_called_once()


def recovery_context(**_options):
    from contextlib import nullcontext
    return nullcontext()


def reopened(lease):
    result = runner.Lease(lease.source, lease.commands, lease.inspect,
                          directory=lease.directory, anchor=lease.capture.anchor, graphics_type='vnc')
    return result


def start(lease):
    lease.view.graphics_type = 'vnc'
    with patch('vm_probe.prepare_maintenance_transport'):
        control.operate(lease, 'start', [])
    lease.release()


@pytest.fixture
def fixture_maintenance_rig(lease_rig, monkeypatch, request):
    """Real controller locks/journal; finite SSH and provisioner doubles only."""
    import fixture_maintenance as maintenance
    from tools import fixture_provision
    lease, current = lease_rig
    start(lease)
    held = reopened(lease)
    control.resume(held, fixture_maintenance=True)
    target = getattr(request, 'param', 'ubuntu')
    guest = held.capture.state['guest']
    guest.update(fixture_boundary='clean', ubuntu_version='26.04')
    if target == 'fedora':
        guest.pop('ubuntu_version')
        guest.update(os_id='fedora', version='44')
    transport = Mock()
    transport.call.side_effect = lambda argv, **kwargs: (
        b'a' * 64 + b'\n' if argv[-1] == fixture_provision.BOOT_SHA256_PROBE else b'{"idle":true}\n')
    maintenance.initialize(held, transport=transport)
    writes = []
    boundary = Mock()
    boundary.call.side_effect = lambda action, request, payloads: writes.append(action)
    monkeypatch.setattr(fixture_provision, 'authenticated_bundle', Mock(return_value={}))
    monkeypatch.setattr(maintenance.fixture_execution.Selection, 'from_record',
                        lambda value: SimpleNamespace(record=lambda: value))

    class Controller:
        failure = False

        def __init__(self, lease, transport, *, register_staging, boundary):
            self.lease, self.boundary, self.register = lease, boundary, register_staging
            self.receipt = None

        def resume_maintenance(self, selection, subsets, *, attempt_id, expected_binding,
                               maintenance_owner):
            assert maintenance._load(self.lease)['phase'] == 'pending'
            assert maintenance_owner(expected_binding) is True
            self.receipt = fixture_provision.Readiness(expected_binding, {})
            return self.receipt

        def provision(self, selection, subsets, *, attempt_id):
            binding = (self.receipt.binding if self.receipt else dict(
                run=held.state['run'], vm_uuid=UUID, boot_sha256='a' * 64,
                generation=0, attempt_id=attempt_id, subsets=list(subsets)))
            if not self.receipt:
                self.register('/run/onpc-fixture-' + 'b' * 64)
                self.boundary.call('place', {'binding': binding})
            if self.failure:
                raise TimeoutError('lost-reply')
            return fixture_provision.Readiness(binding, {})

        def replace(self, selection, subsets, *, readiness, maintenance_owner):
            assert maintenance_owner(readiness.binding) is True
            binding = dict(readiness.binding, generation=readiness.binding['generation'] + 1)
            self.register('/run/onpc-fixture-' + 'c' * 64)
            self.boundary.call('replace', {'binding': binding})
            if self.failure:
                raise TimeoutError('lost-reply')
            return fixture_provision.Readiness(binding, {})

        def require_ready(self, receipt):
            assert receipt.binding['boot_sha256'] == 'a' * 64

    monkeypatch.setattr(fixture_provision, 'Provisioner', Controller)
    yield SimpleNamespace(lease=held, original=lease, current=current, transport=transport,
        maintenance=maintenance, writes=writes, boundary=boundary, controller=Controller,
        a={'target': target, 'build_identity': 'a' * 64},
        b={'target': target, 'build_identity': 'b' * 64})
    held.release()


@pytest.mark.parametrize('fixture_maintenance_rig', ['ubuntu', 'fedora'], indirect=True)
def test_fixture_refresh_persists_generation_across_owned_cli_calls(fixture_maintenance_rig):
    rig = fixture_maintenance_rig
    sync = lambda selection: rig.maintenance.synchronize(
        rig.lease, selection, transport=rig.transport, boundary=rig.boundary)
    initial = sync(rig.a)
    rig.lease.release()
    next_lease = reopened(rig.original)
    try:
        control.resume(next_lease, fixture_maintenance=True)
        # The shared lease rig persists legacy guest metadata. Carry this
        # fixture's clean target declaration across the real controller reopen.
        next_lease.capture.state['guest'] = dict(rig.lease.capture.state['guest'])
        rig.lease = next_lease
        replaced = sync(rig.b)
        repeated = sync(rig.b)
        assert initial.binding['generation'] == 0
        assert replaced.binding == repeated.binding
        assert replaced.binding['generation'] == 1
        assert rig.writes == ['place', 'replace']
        record = rig.maintenance._load(next_lease)
        assert record['phase'] == 'ready' and record['retained'] == [rig.a, rig.b]
        assert len(record['staging']) == 2
        assert rig.current['id'] == 71
        assert rig.original.source.domain.revertToSnapshot.call_count == 1
    finally:
        next_lease.release()


@pytest.mark.parametrize('fault', ['installed', 'release', 'wrong-input'])
def test_fedora_fixture_refresh_refuses_incompatible_baseline_or_input(
        fixture_maintenance_rig, fault):
    rig = fixture_maintenance_rig
    guest = rig.lease.capture.state['guest']
    guest.pop('ubuntu_version')
    guest.update(os_id='fedora', version='44')
    if fault == 'installed':
        guest['fixture_boundary'] = 'installed'
    elif fault == 'release':
        guest['version'] = '43'
    with pytest.raises(runner.Error, match='fixture-maintenance:'):
        if fault == 'wrong-input':
            rig.maintenance.synchronize(rig.lease, rig.a,
                transport=rig.transport, boundary=rig.boundary)
        else:
            rig.maintenance.initialize(rig.lease, transport=rig.transport)
    assert not rig.writes


@pytest.mark.parametrize('fault', ['session', 'worker', 'unknown-owner', 'subset', 'corrupt-input'])
def test_fixture_refresh_refuses_uncertain_or_busy_activity_before_writes(
        fixture_maintenance_rig, fault, monkeypatch):
    rig = fixture_maintenance_rig
    kwargs = dict(transport=rig.transport, boundary=rig.boundary)
    if fault == 'session':
        rig.transport.call.side_effect = lambda argv, **kwargs: (
            b'a' * 64 + b'\n' if argv[-1] != rig.maintenance.SESSION_PROBE else b'busy\n')
    elif fault == 'worker':
        # Any arbitrary action capable of starting a worker permanently retires
        # the dedicated lineage before that action receives guest input.
        rig.maintenance.invalidate(rig.lease)
    elif fault == 'unknown-owner':
        path = rig.lease.directory / rig.maintenance.NAME
        record = json.loads(path.read_bytes())
        record['owner']['run'] = 'f' * 32
        path.write_bytes(runner.baseline.encode(record))
    elif fault == 'subset':
        kwargs['subsets'] = ('trusted-soft',)
    else:
        monkeypatch.setattr(rig.maintenance.fixture_provision, 'authenticated_bundle',
                            Mock(side_effect=ValueError('corrupt-input')))
    with pytest.raises((runner.Error, ValueError)):
        rig.maintenance.synchronize(rig.lease, rig.a, **kwargs)
    assert rig.writes == []


def test_fixture_refresh_other_launcher_cannot_adopt_locked_maintenance(fixture_maintenance_rig):
    rig = fixture_maintenance_rig
    competitor = reopened(rig.original)
    try:
        with pytest.raises(runner.Error, match='busy-controller'):
            control.resume(competitor, fixture_maintenance=True)
        assert rig.writes == []
    finally:
        competitor.release()


@pytest.mark.parametrize('interrupted', [False, True])
@pytest.mark.parametrize('fixture_maintenance_rig', ['ubuntu', 'fedora'], indirect=True)
def test_independent_fixture_runtime_use_is_persistently_owned(
        fixture_maintenance_rig, monkeypatch, interrupted):
    import fixture_live_refresh_qualification as qualification
    rig = fixture_maintenance_rig
    receipt = rig.maintenance.synchronize(rig.lease, rig.a,
        transport=rig.transport, boundary=rig.boundary)
    monkeypatch.setattr(qualification.proof, 'audit', lambda *args: {'accounts': {}})
    monkeypatch.setattr(qualification.proof, 'validate_readback', lambda *args, **kwargs: {})
    def witness(*args):
        assert rig.maintenance._load(rig.lease)['phase'] == 'pending'
        assert args[-1] == rig.a['target']
        if interrupted:
            raise TimeoutError('uncertain independent runtime reply')
        return {'owned_process_closed': True}
    monkeypatch.setattr(qualification.proof, 'runtime_witnesses', witness)
    if interrupted:
        with pytest.raises(TimeoutError):
            qualification.observed_runtime(rig.lease, rig.transport,
                {'inputs': {'target': {'os': rig.a['target']}}}, receipt)
    else:
        qualification.observed_runtime(rig.lease, rig.transport,
            {'inputs': {'target': {'os': rig.a['target']}}}, receipt)
    assert rig.maintenance._load(rig.lease)['phase'] == ('unavailable' if interrupted else 'ready')


def test_fixture_refresh_reuses_initial_transport_without_reopening_ssh_files(
        fixture_maintenance_rig, monkeypatch):
    import vm_probe
    rig = fixture_maintenance_rig
    monkeypatch.setattr(vm_probe, 'connect', Mock(side_effect=AssertionError('SSH reopened')))
    assert rig.maintenance.transport_for(rig.lease) is rig.transport
    rig.maintenance.synchronize(rig.lease, rig.a, boundary=rig.boundary)
    assert rig.writes == ['place']


def test_fixture_refresh_reconstruction_uncertainty_latches_before_fixture_witness(
        fixture_maintenance_rig, monkeypatch):
    rig = fixture_maintenance_rig
    kwargs = dict(transport=rig.transport, boundary=rig.boundary)
    rig.maintenance.synchronize(rig.lease, rig.a, **kwargs)

    def interrupted(self, *args, **kwargs):
        assert rig.maintenance._load(rig.lease)['phase'] == 'pending'
        raise KeyboardInterrupt('interrupted-fixture-witness')

    monkeypatch.setattr(rig.controller, 'resume_maintenance', interrupted)
    with pytest.raises(KeyboardInterrupt):
        rig.maintenance.synchronize(rig.lease, rig.b, **kwargs)
    assert rig.maintenance._load(rig.lease)['phase'] == 'unavailable'
    with pytest.raises(runner.Error, match='unavailable-until-owned-stop'):
        rig.maintenance.synchronize(rig.lease, rig.a, **kwargs)
    assert rig.writes == ['place']


@pytest.mark.parametrize('action', ['reboot', 'send-key'])
def test_arbitrary_maintenance_action_retires_fixture_refresh_before_input(
        fixture_maintenance_rig, monkeypatch, action):
    import vm_probe
    rig = fixture_maintenance_rig
    rig.lease.release()
    held = reopened(rig.original)
    transport = Mock()
    monkeypatch.setattr(vm_probe, 'connect', lambda lease: transport)

    def check_retired(*args):
        assert rig.maintenance._load(held)['phase'] == 'unavailable'

    transport.reboot.side_effect = check_retired
    rig.original.source.domain.sendKey.side_effect = check_retired
    try:
        control.operate(held, action, [28] if action == 'send-key' else [])
        assert rig.maintenance._load(held)['phase'] == 'unavailable'
    finally:
        held.release()


def test_fixture_refresh_lost_reply_retains_both_inputs_until_owned_stop(fixture_maintenance_rig):
    rig = fixture_maintenance_rig
    kwargs = dict(transport=rig.transport, boundary=rig.boundary)
    rig.maintenance.synchronize(rig.lease, rig.a, **kwargs)
    rig.controller.failure = True
    with pytest.raises(TimeoutError):
        rig.maintenance.synchronize(rig.lease, rig.b, **kwargs)
    record = rig.maintenance._load(rig.lease)
    assert record['phase'] == 'unavailable' and record['retained'] == [rig.a, rig.b]
    rig.lease.release()
    resumed = reopened(rig.original)
    try:
        control.resume(resumed, fixture_maintenance=True)
        with pytest.raises(runner.Error, match='unavailable-until-owned-stop'):
            rig.maintenance.synchronize(resumed, rig.b, **kwargs)
        assert rig.writes == ['place', 'replace']
    finally:
        resumed.release()
    stopped = reopened(rig.original)
    try:
        with patch('vm_probe.connect', lambda lease: None):
            control.operate(stopped, 'stop', [])
        assert stopped.state['phase'] == 'complete' and rig.current['id'] == -1
        assert not (stopped.directory / rig.maintenance.NAME).exists()
    finally:
        stopped.release()


@pytest.mark.parametrize('fault', [None, 'running', 'run', 'baseline', 'domain',
                                  'snapshot', 'configuration', 'guest', 'record-link'])
def test_completed_off_maintenance_stop_recovers_interrupted_record_cleanup(
        fixture_maintenance_rig, monkeypatch, fault):
    import fixture_live_refresh_qualification as qualification
    rig = fixture_maintenance_rig
    receipt = rig.maintenance.synchronize(rig.lease, rig.a,
        transport=rig.transport, boundary=rig.boundary)
    monkeypatch.setattr(qualification.fixture_execution, 'validate_source_selection',
                        lambda value, selection: value)
    rig.original.source.domain.listAllSnapshots.return_value = []
    qualification.write_checkpoint(rig.lease, SimpleNamespace(record=lambda: rig.a), {}, receipt)
    rig.lease.release()
    stopped = reopened(rig.original)
    try:
        with patch('vm_probe.connect', lambda lease: None), patch.object(
                qualification, 'cleanup_checkpoint', side_effect=KeyboardInterrupt('cleanup interrupted')):
            with pytest.raises(KeyboardInterrupt, match='cleanup interrupted'):
                control.operate(stopped, 'stop', [])
        assert stopped.state['phase'] == 'complete' and rig.current['id'] == -1
    finally:
        stopped.release()
    paths = [stopped.directory / name for name in (rig.maintenance.NAME, qualification.NAME)]
    before = [path.read_bytes() for path in paths]
    if fault == 'running':
        rig.original.source.off, rig.current['id'] = False, stopped.state['domain_id']
    elif fault == 'run':
        path = stopped.directory / 'vm-control.json'
        owner = json.loads(path.read_bytes())
        owner['run'] = 'f' * 32
        path.write_bytes(runner.baseline.encode(owner))
    elif fault in ('baseline', 'domain'):
        state = json.loads(stopped.journal.read_bytes())
        state['baseline_sha256' if fault == 'baseline' else 'domain_uuid'] = 'f' * (64 if fault == 'baseline' else 36)
        stopped.journal.write_bytes(runner.baseline.encode(state))
    elif fault == 'snapshot':
        rig.original.source.baseline_xml += ' '
    elif fault == 'configuration':
        rig.current['xml'] = rig.current['xml'].replace('</domain>', '<description>foreign</description></domain>')
    elif fault == 'record-link':
        saved = paths[1].with_name('displaced-checkpoint.json')
        paths[1].rename(saved)
        paths[1].symlink_to(saved.name)
    held = reopened(rig.original)
    if fault == 'guest':
        held.inspect = Mock(return_value={})
    journal_before = stopped.journal.read_bytes()
    snapshots = rig.original.source.domain.revertToSnapshot.call_count
    definitions = rig.original.source.connection.defineXML.call_count
    shutdowns = rig.original.source.shutdown_calls
    starts = rig.original.source.domain.create.call_count
    try:
        if fault:
            with pytest.raises(runner.Error):
                control.operate(held, 'stop', [])
            assert [path.read_bytes() for path in paths] == before
        else:
            control.operate(held, 'stop', [])
            assert held.state['phase'] == 'complete'
            assert all(not path.exists() for path in paths)
        assert stopped.journal.read_bytes() == journal_before
        assert rig.original.source.domain.revertToSnapshot.call_count == snapshots
        assert rig.original.source.connection.defineXML.call_count == definitions
        assert rig.original.source.shutdown_calls == shutdowns
        assert rig.original.source.domain.create.call_count == starts
    finally:
        held.release()


@pytest.mark.parametrize('phase', [
    'validated', 'shutdown-requested', 'restore-requested', 'isolated', 'ssh-bootstrap',
    'start-requested', 'cleanup-requested'])
@pytest.mark.parametrize('fault', [None, 'running', 'owner', 'configuration'])
def test_preparation_recovers_never_started_owned_maintenance_without_booting(
        lease_rig, phase, fault):
    lease, current = lease_rig
    lease.view.graphics_type = 'vnc'
    lease.__enter__()
    control.save_owner(lease)
    if phase in ('isolated', 'ssh-bootstrap', 'start-requested', 'cleanup-requested'):
        lease.prepare()
    lease.save(phase)
    lease.release()
    before = lease.journal.read_bytes()
    if fault == 'running':
        current['id'] = 71
        lease.source.off = False
        lease.source.domain.listAllSnapshots.return_value = []
    elif fault == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    elif fault == 'configuration':
        current['xml'] = current['xml'].replace('</domain>', '<description>unrelated</description></domain>')
    held = reopened(lease)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    try:
        if fault:
            with pytest.raises(RuntimeError):
                control.recover_preparation(held)
            assert lease.journal.read_bytes() == before
            assert lease.source.domain.revertToSnapshot.call_count == snapshots
        else:
            control.recover_preparation(held)
            assert held.state['phase'] == 'complete'
            assert current['id'] == -1
    finally:
        held.release()
    lease.source.domain.create.assert_not_called()


def test_start_reboot_input_stop_share_one_attempt_and_restore_only_at_edges(lease_rig, monkeypatch):
    import vm_probe
    lease, current = lease_rig
    transport = Mock()
    def connect(held):
        held.shutdown_request = transport.poweroff
        return transport
    monkeypatch.setattr(vm_probe, 'connect', connect)
    monkeypatch.setattr(runner.baseline, 'digest', Mock(side_effect=AssertionError('image hash')))
    lease.commands.check = Mock(side_effect=AssertionError('image scan'))
    original = current['xml']
    start(lease)
    assert lease.state['phase'] == 'running'
    run = lease.state['run']
    for action, keys in [('reboot', []), ('send-key', [28])]:
        resumed = reopened(lease)
        try:
            control.operate(resumed, action, keys)
            assert resumed.state['run'] == run
            assert resumed.capture.verification_totals['bytes_read'] == 0
        finally:
            resumed.release()
    assert lease.source.domain.revertToSnapshot.call_count == 1
    transport.reboot.assert_called_once_with()
    lease.source.domain.reboot.assert_not_called()
    lease.source.domain.sendKey.assert_called_once_with(
        lease.source.api.VIR_KEYCODE_SET_LINUX, 100, [28], 1, 0)
    resumed = reopened(lease)
    try:
        control.operate(resumed, 'stop', [])
    finally:
        resumed.release()
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert current['xml'] == original
    assert resumed.state['phase'] == 'complete'
    assert resumed.capture.verification_totals['bytes_read'] == 0
    assert lease.source.off
    transport.poweroff.assert_called_once_with()


@pytest.mark.parametrize('phase', ['running', 'cleanup-requested'])
@pytest.mark.parametrize('restored', [False, True])
def test_off_maintenance_recovery_audits_restored_guest_or_restores_owned_isolation(
        lease_rig, phase, restored):
    lease, current = lease_rig
    start(lease)
    lease.state['phase'] = phase
    lease.journal.write_bytes(runner.baseline.encode(lease.state))
    if restored:
        lease.source.domain.revertToSnapshot(None, 0)
    else:
        lease.source.off, current['id'] = True, -1
    held = reopened(lease)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    definitions = lease.source.connection.defineXML.call_count
    shutdowns = lease.source.shutdown_calls
    try:
        control.recover_preparation(held)
        assert held.state['phase'] == 'complete'
        assert current['id'] == -1
        assert lease.source.domain.revertToSnapshot.call_count == snapshots + int(not restored)
        assert lease.source.connection.defineXML.call_count == definitions + int(not restored)
        assert lease.source.shutdown_calls == shutdowns
    finally:
        held.release()
    lease.source.domain.create.assert_called_once()
    lease.source.domain.destroyFlags.assert_not_called()


@pytest.mark.parametrize('fault', [
    'guest', 'audit-interrupted', 'restarted', 'configuration', 'split-configuration',
    'owner', 'snapshot', 'busy'])
def test_restored_off_maintenance_refusals_preserve_journal_without_vm_mutation(
        lease_rig, fault):
    lease, current = lease_rig
    start(lease)
    lease.source.domain.revertToSnapshot(None, 0)
    before = lease.journal.read_bytes()
    held = reopened(lease)
    competitor = reopened(lease)
    original = current['xml']
    if fault == 'guest':
        held.inspect = Mock(return_value={})
    elif fault == 'audit-interrupted':
        held.inspect = Mock(side_effect=KeyboardInterrupt())
    elif fault == 'restarted':
        def restart(*args):
            lease.source.off, current['id'] = False, 72
            return lease.capture.state['guest']
        held.inspect = restart
    elif fault == 'configuration':
        current['xml'] = original.replace('</domain>', '<description>unrelated</description></domain>')
    elif fault == 'split-configuration':
        lease.source.domain.XMLDesc.side_effect = lambda flags=0: (
            original if flags else original.replace('</domain>', '<description>unrelated</description></domain>'))
    elif fault == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    elif fault == 'snapshot':
        lease.source.baseline_xml += ' '
    else:
        control.resume(competitor, stopping=True)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    definitions = lease.source.connection.defineXML.call_count
    shutdowns = lease.source.shutdown_calls
    try:
        with pytest.raises(KeyboardInterrupt if fault == 'audit-interrupted' else RuntimeError):
            control.recover_preparation(held)
        assert lease.journal.read_bytes() == before
        assert lease.source.domain.revertToSnapshot.call_count == snapshots
        assert lease.source.connection.defineXML.call_count == definitions
        assert lease.source.shutdown_calls == shutdowns
        lease.source.domain.destroyFlags.assert_not_called()
        lease.source.domain.create.assert_called_once()
    finally:
        held.release()
        competitor.release()


@pytest.mark.parametrize('fault', [None, 'instance', 'owner', 'busy'])
def test_automatic_preparation_recovery_stops_only_proven_maintenance(
        lease_rig, tmp_path, monkeypatch, fault):
    import check_graphical_recovery as recovery
    import vm_probe
    monkeypatch.setattr(recovery, 'recovery_session', recovery_context)
    monkeypatch.setattr(vm_probe, 'connect',
                        lambda held: setattr(held, 'shutdown_request', Mock()))
    lease, current = lease_rig
    start(lease)
    before = lease.journal.read_bytes()
    if fault == 'instance':
        current['id'] += 1
    elif fault == 'owner':
        owner = json.loads((lease.directory / 'vm-control.json').read_bytes())
        owner['baseline_sha256'] = 'f' * 64
        (lease.directory / 'vm-control.json').write_text(json.dumps(owner))
    evidence = tmp_path / 'recovery-evidence'
    evidence.mkdir()
    recovered = reopened(lease)
    monkeypatch.setattr(recovery, 'allocate', lambda *a, **kw: str(evidence))
    monkeypatch.setattr(recovery.os, 'umask', Mock())
    monkeypatch.setattr(recovery.threading, 'Thread', Mock())
    monkeypatch.setattr(recovery.importlib, 'import_module', lambda _: Mock())
    monkeypatch.setattr(recovery.runner.baseline, 'LibvirtSource', lambda _: lease.source)
    monkeypatch.setattr(recovery.runner, 'Commands', lambda: lease.commands)
    monkeypatch.setattr(recovery.runner, 'Lease', lambda *a, **kw: recovered)
    # Online maintenance has SPICE first and private VNC beside its observer.
    monkeypatch.setattr(recovery, 'recorded_graphics_type', lambda _: 'spice')
    lease.source.close = Mock()
    competitor = reopened(lease)
    if fault == 'busy':
        control.resume(competitor)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    try:
        assert recovery.recover(None, maintenance=True) == int(fault is not None)
    finally:
        competitor.release()
    result = json.loads((evidence / 'result.json').read_bytes())
    assert result['scope'] == 'recorded-maintenance-cleanup-only'
    if fault:
        assert lease.journal.read_bytes() == before
        assert lease.source.domain.revertToSnapshot.call_count == snapshots
    else:
        assert json.loads(lease.journal.read_bytes())['phase'] == 'complete'
        assert current['id'] == -1
    assert recovered.fd is None


@pytest.mark.parametrize('phase', ['running', 'isolated', 'cleanup-requested'])
@pytest.mark.parametrize('fault', [None, 'owner', 'snapshot', 'busy', 'interrupted'])
def test_auto_baseline_recovers_off_maintenance_and_preserves_refused_attempts(
        lease_rig, monkeypatch, phase, fault):
    lease, current = lease_rig
    lease.view.graphics_type = 'vnc'
    lease.__enter__()
    control.save_owner(lease)
    lease.prepare()
    if phase == 'running':
        lease.start()
        lease.source.off, current['id'] = True, -1
    lease.save(phase)
    lease.release()
    before = lease.journal.read_bytes()
    owner_path = lease.directory / 'vm-control.json'
    if fault == 'owner':
        owner = json.loads(owner_path.read_bytes())
        owner['baseline_sha256'] = 'f' * 64
        owner_path.write_bytes(runner.baseline.encode(owner))
    elif fault == 'snapshot':
        lease.source.baseline_xml += ' '
    owner_before = owner_path.read_bytes()
    held, competitor = reopened(lease), reopened(lease)
    if fault == 'busy':
        control.resume(competitor, stopping=True)
    elif fault == 'interrupted':
        held.inspect = Mock(side_effect=KeyboardInterrupt())
    monkeypatch.setattr(runner.baseline.guest_contract.vm_config, 'selected',
                        lambda **_: SimpleNamespace(baseline_directory=lease.directory))
    monkeypatch.setattr(runner, 'Lease', lambda *a, **kw: held)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    starts = lease.source.domain.create.call_count
    try:
        if fault:
            with pytest.raises(KeyboardInterrupt if fault == 'interrupted' else runner.Error):
                runner.baseline.recover_off_attempt(
                    lease.source, lease.commands, lease.inspect, mode='auto')
            if fault != 'interrupted':
                assert lease.journal.read_bytes() == before
                assert lease.source.domain.revertToSnapshot.call_count == snapshots
            else:
                assert json.loads(lease.journal.read_bytes())['phase'] == 'cleanup-requested'
        else:
            assert runner.baseline.recover_off_attempt(
                lease.source, lease.commands, lease.inspect, mode='auto') is True
            completed = lease.journal.read_bytes()
            assert json.loads(completed)['phase'] == 'complete'
            assert current['id'] == -1
            assert lease.source.domain.revertToSnapshot.call_count == snapshots + 1
            assert runner.baseline.recover_off_attempt(
                lease.source, lease.commands, lease.inspect, mode='auto') is None
            assert lease.journal.read_bytes() == completed
            assert lease.source.domain.revertToSnapshot.call_count == snapshots + 1
        assert owner_path.read_bytes() == owner_before
        assert lease.source.domain.create.call_count == starts
        assert held.fd is held.compatibility_fd is None
    finally:
        held.release()
        competitor.release()


@pytest.mark.parametrize('mutation', ['instance', 'run', 'owner', 'baseline', 'symlink'])
def test_replacement_or_unowned_attempt_never_receives_vm_actions(lease_rig, mutation):
    lease, current = lease_rig
    start(lease)
    if mutation == 'instance':
        current['id'] += 1
    elif mutation == 'run':
        current['xml'] = current['xml'].replace(lease.state['run'], 'f' * 32)
        # A foreign tag has no private saved-memory proof to authorize cleanup.
        lease.source.domain.listAllSnapshots.return_value = []
    elif mutation == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    elif mutation == 'baseline':
        lease.source.baseline_xml += ' '
    else:
        owner = lease.directory / 'vm-control.json'
        owner.rename(lease.directory / 'old-owner.json')
        owner.symlink_to('old-owner.json')
    resumed = reopened(lease)
    before = lease.source.shutdown_calls
    try:
        with pytest.raises(runner.Error):
            control.operate(resumed, 'stop', [])
    finally:
        resumed.release()
    assert lease.source.shutdown_calls == before
    lease.source.domain.destroyFlags.assert_not_called()
    assert lease.source.domain.revertToSnapshot.call_count == 1


def test_busy_controller_lock_refuses_even_with_valid_identity(lease_rig):
    lease, _ = lease_rig
    lease.view.graphics_type = 'vnc'
    with patch('vm_probe.prepare_maintenance_transport'):
        control.operate(lease, 'start', [])
    concurrent = reopened(lease)
    try:
        with pytest.raises(runner.Error, match='busy-controller'):
            control.operate(concurrent, 'stop', [])
    finally:
        concurrent.release()
        lease.release()
    assert lease.source.domain.revertToSnapshot.call_count == 1


def test_wrong_vm_uuid_or_connection_refuses_before_leasing():
    source = Mock(uuid=UUID)
    source.connection.getURI.return_value = 'qemu:///system'
    source.domain.UUIDString.return_value = UUID
    source.domain.name.return_value = runner.baseline.DOMAIN
    control.check_identity(source, UUID)
    for uri, expected, name in [('qemu:///session', UUID, runner.baseline.DOMAIN),
                                 ('qemu:///system', 'f' * 36, runner.baseline.DOMAIN),
                                 ('qemu:///system', UUID, 'other-vm')]:
        source.connection.getURI.return_value = uri
        source.domain.name.return_value = name
        with pytest.raises(runner.Error):
            control.check_identity(source, expected)


@pytest.mark.parametrize('argv', [['vm', 'destroy', 'other'], ['vm', 'start', '1'],
                                 ['vm', '--domain=other', 'start'], ['vm', 'send-key'],
                                 ['vm', 'send-key', '256'], ['vm', 'send-key', '-1']])
def test_dispatcher_refuses_arbitrary_vm_selection_and_actions(argv):
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    with pytest.raises(ValueError):
        dispatcher['selection'](root, [*argv, *VM_ARGS])


def test_dispatcher_supplies_installed_uuid_and_no_caller_uri():
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    select = dispatcher['selection']
    with pytest.raises(ValueError, match='refresh'):
        select(root, ['vm', 'start', *VM_ARGS])
    select.__globals__['VM_UUIDS'] = {vm_name(): UUID}
    command = select(root, ['vm', 'send-key', '28', *VM_ARGS])
    assert command[3:] == [*VM_ARGS, '--expected-uuid', UUID, 'send-key', '28']
    for action in ('reproduce-gdm-denial', 'reproduce-kiosk-entry', 'reproduce-kiosk-refusal', 'reproduce-kiosk-approval', 'probe-kiosk-approval',
                   'reproduce-kiosk-preferences',
                   'reproduce-station-shortcuts',
                   'reproduce-baseline-app-effects',
                   'reproduce-baseline-auth-pause',
                   'reproduce-lock-denial', 'reproduce-retained-entry',
                   'reproduce-retained-app-visits',
                   'reproduce-revoke-cancel', 'probe-revoke-balances',
                   'reproduce-countdown-minutes',
                   'reproduce-natural-expiry',
                   'reproduce-countdown-resume',
                   'reproduce-retained-unlock',
                   'probe-retained-app-launch',
                   'probe-lock-curtain', 'reproduce-transfer-refusal', 'probe-transfer-refusal',
                   'reproduce-riley-native-grid', 'probe-riley-native-grid',
                   'reproduce-remembered-return', 'probe-remembered-return', 'repeat-remembered-return',
                   'enter-remembered-return'):
        command = select(root, ['vm', action, *VM_ARGS])
        assert command[3:] == [*VM_ARGS, '--expected-uuid', UUID, action]
        with pytest.raises(ValueError):
            select(root, ['vm', action, '1', *VM_ARGS])

    for action in ('probe-kiosk-latency', 'probe-kiosk-prompt-latency'):
        for counts in ([], ['1'], ['10'], ['10', '0'], ['10', '1']):
            command = select(root, ['vm', action, *counts, *VM_ARGS])
            assert command[3:] == [*VM_ARGS, '--expected-uuid', UUID, action, *counts]
        for counts in (['0'], ['11'], ['1', '2']):
            with pytest.raises(ValueError):
                select(root, ['vm', action, *counts, *VM_ARGS])


@pytest.mark.parametrize('boot', ['a' * 64, 'b' * 64])
def test_logout_identity_requires_current_boot_and_both_real_invocations(boot):
    import vm_probe
    transport = Mock()
    invocations = {'app': 'b' * 32, 'compositor': 'c' * 32}
    transport.call.return_value = json.dumps({'boot_sha256': boot, 'invocations': invocations})
    if boot != 'a' * 64:
        with pytest.raises(runner.Error, match='logout-identity'):
            vm_probe.logout_identity(transport, 'a' * 64)
    else:
        assert vm_probe.logout_identity(transport, boot) == invocations


def test_kiosk_approval_reproduction_stops_before_qualification_and_secret_input(monkeypatch):
    import vm_probe
    from request_flow import RequestFlowJourney
    from kiosk_approved_flow import PLAN
    reproduce = Mock()
    monkeypatch.setattr(vm_probe, 'reproduce_denial', reproduce)
    lease = object()
    vm_probe.reproduce_kiosk_approval(lease)
    reproduce.assert_called_once_with(lease, RequestFlowJourney, PLAN,
                                     'approval-qualified', 'kiosk-approval', native_log=True)
    prefix = list(PLAN.stages[:PLAN.stages.index('approval-qualified')])
    assert prefix[-1] == 'approval-open'
    assert PLAN.screen_tags['approval-open'] == 'ui:kiosk-mate-open'
    assert not {'approval-rechecked', 'approval-success'} & set(prefix)


@pytest.mark.parametrize('surface', ['baseline-app-effects', 'baseline-auth-pause'])
def test_baseline_diagnostic_dispatch_resumes_owned_lease_and_releases_controller(
        monkeypatch, tmp_path, surface):
    import vm_probe
    import tools.test_storage as storage
    api, source, lease, commands = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(control.importlib, 'import_module', lambda name: api)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.os, 'getegid', lambda: 0)
    monkeypatch.setattr(control.os, 'umask', Mock())
    monkeypatch.setattr(control.threading, 'Thread', Mock())
    monkeypatch.setattr(control.runner.baseline, 'LibvirtSource', lambda value: source)
    monkeypatch.setattr(control.runner, 'Commands', lambda: commands)
    monkeypatch.setattr(control.runner, 'Lease', lambda *args, **kwargs: lease)
    monkeypatch.setattr(storage, 'scratch_directory', lambda: tmp_path)
    monkeypatch.setattr(control.tempfile, 'mkdtemp', lambda **kwargs: str(tmp_path))
    identity, resume, reproduce, operate = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(control, 'check_identity', identity)
    monkeypatch.setattr(control, 'resume', resume)
    monkeypatch.setattr(control, 'operate', operate)
    monkeypatch.setattr(vm_probe, 'reproduce_' + surface.replace('-', '_'), reproduce)
    assert control.main([*VM_ARGS, '--expected-uuid', UUID,
                         'reproduce-' + surface]) == 0
    identity.assert_called_once_with(source, UUID)
    resume.assert_called_once_with(lease)
    reproduce.assert_called_once_with(lease)
    operate.assert_not_called()  # Retained maintenance still needs explicit stop.
    source.domain.shutdown.assert_not_called()
    source.domain.destroyFlags.assert_not_called()
    lease.release.assert_called_once_with()
    source.close.assert_called_once_with()


@pytest.mark.parametrize('refused', [False, True])
@pytest.mark.parametrize('worker_stopped,callback_closed', [(True, True), (False, True), (True, False)])
def test_auth_pause_boundary_uses_original_session_guard_without_acceptance(
        tmp_path, monkeypatch, capsys, refused, worker_stopped, callback_closed):
    from contextlib import nullcontext
    import vm_probe
    import fixture_credentials
    import e2e_worker
    import qualification_storage
    import session_control
    import ui_observations
    from baseline_auth_pause import PLAN
    monkeypatch.setattr(qualification_storage, 'recovery_session', recovery_context)
    monkeypatch.setattr(qualification_storage, 'allocate', lambda *_args, **_kwargs: str(tmp_path))
    credentials = Mock()
    monkeypatch.setattr(fixture_credentials, 'FixtureCredentials', Mock(return_value=credentials))
    transport = object()
    monkeypatch.setattr(vm_probe, 'connect', Mock(return_value=transport))
    result = {'operation': 'parent-entry-retained', 'outcome': 'passed'}
    observe = Mock(side_effect=RuntimeError('session:source-changed') if refused else None,
                   return_value=result)
    monkeypatch.setattr(session_control, 'observe', observe)
    ui = Mock()
    monkeypatch.setattr(ui_observations, 'UiObservations', ui)
    boundary = 'return-entry-guard'
    prefix = PLAN.stages[:PLAN.stages.index(boundary)]
    class Journey:
        def __init__(self, context, progress, *, plan):
            self.plan, self.failed = plan, False
            self.steps = [{'stage': stage} for stage in prefix]
        def step(self, guard):
            pytest.fail('diagnosis must not advance the boundary or accept the journey')
    def run(directory, lease, ledger, **kwargs):
        assert kwargs['maintenance'] is True
        assert kwargs['timeout'] == 900
        assert kwargs['credentials'] is credentials
        (directory / (boundary + '.request.json')).write_text(json.dumps(
            {'stage': boundary, 'screenshot': None}))
        assert kwargs['guarded_observe'](Mock()) is True
        kwargs['validate']()
        assert not (directory / (boundary + '.reply.json')).exists()
        observe.assert_called_once_with(transport, 'parent-entry-retained')
        ui.assert_not_called()
        return {'worker_stopped': worker_stopped, 'callback_closed': callback_closed}
    monkeypatch.setattr(e2e_worker, 'run_distribution', run)
    lease = SimpleNamespace(commands=SimpleNamespace(directory=None), guard=Mock())
    if worker_stopped and callback_closed:
        vm_probe.reproduce_denial(lease, Journey, PLAN, boundary, 'baseline-auth-pause',
            boundary_operation='system:parent-entry-retained')
        assert 'scene retained; evidence=' in capsys.readouterr().out
    else:
        with pytest.raises(runner.Error, match='diagnosis:cleanup-incomplete'):
            vm_probe.reproduce_denial(lease, Journey, PLAN, boundary, 'baseline-auth-pause',
                boundary_operation='system:parent-entry-retained')
        assert 'scene retained' not in capsys.readouterr().out
    credentials.provision_online.assert_called_once_with(lease, transport)
    retained = json.loads((tmp_path / 'boundary-observation.json').read_text())
    assert retained == ({'outcome': 'refused', 'error_type': 'RuntimeError'} if refused else result)


@pytest.mark.parametrize('surface,boundary,operation,binding', [
    ('kiosk-entry', 'return-entry-guard', 'system:parent-entry-retained', 'system:parent-entry-retained'),
    ('baseline-auth-pause', 'request-form', 'system:parent-entry-retained', 'system:parent-entry-retained'),
    ('baseline-auth-pause', 'return-entry-guard', 'system:parent-entry-fresh', 'system:parent-entry-fresh'),
    ('baseline-auth-pause', 'return-entry-guard', 'system:parent-entry-retained', 'ui:gdm-returned'),
])
def test_auth_pause_system_boundary_refuses_other_contexts(surface, boundary, operation, binding):
    import vm_probe
    plan = SimpleNamespace(screen_tags={boundary: binding})
    with pytest.raises(runner.Error, match='diagnosis:system-boundary-binding'):
        vm_probe.reproduce_denial(None, object, plan, boundary, surface, boundary_operation=operation)


@pytest.mark.parametrize('fault', [None, 'before-ready', 'after-ready', 'wrong-boot', 'partial', 'oversize'])
def test_retained_unlock_capture_has_private_command_owner_and_waits_for_completion(
        tmp_path, monkeypatch, fault):
    from retained_unlock_capture import Capture
    import vm_transport
    boot = 'a' * 64
    complete = __import__('threading').Event()
    source = SimpleNamespace(config={'run': 'owned'}, commands=SimpleNamespace(lock_fd=17), guard=Mock())
    lease = SimpleNamespace(guard=Mock())
    ready = {'event': 'ready', 'monotonic_ns': 100, 'boot_sha256': boot,
        'session_sha256': 'b' * 64, 'screensaver_active': True,
        'session_active': False, 'locked_hint': True}
    if fault == 'wrong-boot':
        ready['boot_sha256'] = 'c' * 64
    def call(argv, **kwargs):
        assert argv == ['/usr/bin/python3', '-I', '-']
        assert kwargs['timeout'] == 75
        # The payload imports no host integration code in the guest.
        compile(kwargs['input'], '<capture>', 'exec')
        try:
            if fault == 'before-ready':
                raise RuntimeError('synthetic-command-error')
            send = kwargs['on_stream']
            raw = (json.dumps(ready) + '\n').encode()
            send(raw[:12], 'stdout')
            send(raw[12:], 'stdout')
            if fault == 'after-ready':
                raise RuntimeError('synthetic-command-error')
            if fault == 'partial':
                send(b'{', 'stdout')
            elif fault == 'oversize':
                send(b'x' * 262145, 'stdout')
            else:
                send(b'{"event":"finished","monotonic_ns":200}\n', 'stdout')
        finally:
            complete.set()
    transport = SimpleNamespace(call=Mock(side_effect=call))
    factory = Mock(return_value=transport)
    monkeypatch.setattr(vm_transport, 'Transport', factory)
    capture = Capture(lease, source, tmp_path)
    if fault:
        try:
            capture.start(boot)
        except runner.Error:
            pass
        with pytest.raises(RuntimeError, match='capture:failed'):
            capture.close()
    else:
        capture.start(boot)
        capture.close()
    assert complete.is_set() and not capture.thread.is_alive()
    config, commands = factory.call_args.args
    assert config == source.config and config is not source.config
    assert commands is not source.commands and commands.lock_fd == 17
    assert commands.directory == tmp_path / 'unlock-capture'
    assert factory.call_args.kwargs == {'guard': source.guard}
    result = json.loads((tmp_path / 'unlock-capture-result.json').read_text())
    assert result['outcome'] == ('failed' if fault else 'captured')
    assert result['ready'] == (fault not in ('before-ready', 'wrong-boot'))
    assert result['timestamp_scope'] == 'guest-observer-dispatch'
    assert result['cross_bus_ordering'] == 'unproven'
    assert json.loads((tmp_path / 'unlock-transitions.json').read_text()) == capture.rows


@pytest.mark.parametrize('failed', [False, True])
@pytest.mark.parametrize('capture_failed', [False, True])
def test_unlock_capture_starts_before_first_recipient_proof_and_closes_after_worker(
        tmp_path, monkeypatch, failed, capture_failed):
    from contextlib import nullcontext
    import vm_probe
    import retained_unlock_capture
    import fixture_credentials
    import e2e_worker
    import qualification_storage
    from desktop_session import RETAINED_UNLOCK_PLAN
    monkeypatch.setattr(qualification_storage, 'recovery_session', recovery_context)
    monkeypatch.setattr(qualification_storage, 'allocate', lambda *_args, **_kwargs: str(tmp_path))
    monkeypatch.setattr(fixture_credentials, 'FixtureCredentials', Mock())
    monkeypatch.setattr(vm_probe, 'connect', Mock(return_value=object()))
    events = []
    capture = SimpleNamespace(
        start=Mock(side_effect=lambda boot: events.append(('capture', boot))),
        close=Mock(side_effect=lambda: events.append(('close', None))))
    if capture_failed:
        def close():
            events.append(('close', None))
            raise RuntimeError('capture-failure')
        capture.close.side_effect = close
    monkeypatch.setattr(retained_unlock_capture, 'Capture', Mock(return_value=capture))
    class Journey:
        def __init__(self, *_args, plan):
            self.plan, self.boot = plan, 'a' * 64
            self.steps = [{'stage': stage} for stage in plan.stages[
                :plan.stages.index('retained-recipient-qualified')]]
        def step(self, guard):
            return self._step(guard)
        def _step(self, guard):
            events.append(('proof', None))
    def run(directory, lease, ledger, **kwargs):
        # Polls before the request must not launch capture.
        kwargs['guarded_observe'](Mock())
        assert events == [('proof', None)]
        events.clear()
        (directory / 'retained-recipient-qualified.request.json').write_text('{}')
        kwargs['guarded_observe'](Mock())
        assert events == [('capture', 'a' * 64), ('proof', None)]
        events.append(('worker-stopped', None))
        if failed:
            raise runner.Error('worker-refused')
        return {'worker_stopped': True, 'callback_closed': True}
    monkeypatch.setattr(e2e_worker, 'run_distribution', run)
    lease = SimpleNamespace(commands=SimpleNamespace(directory=None), guard=Mock())
    if failed or capture_failed:
        with pytest.raises(RuntimeError, match='worker-refused' if failed else 'capture-failure'):
            vm_probe.reproduce_denial(lease, Journey, RETAINED_UNLOCK_PLAN, 'unlock-desktop',
                'retained-unlock', boundary_operation='child-retained-unlock-diagnostic', unlock_capture=True)
    else:
        vm_probe.reproduce_denial(lease, Journey, RETAINED_UNLOCK_PLAN, 'unlock-desktop',
            'retained-unlock', boundary_operation='child-retained-unlock-diagnostic', unlock_capture=True)
    assert events[-2:] == [('worker-stopped', None), ('close', None)]
    capture.start.assert_called_once_with('a' * 64)
    capture.close.assert_called_once_with()


def test_unlock_capture_refuses_other_reproduction_boundaries():
    import vm_probe
    with pytest.raises(runner.Error, match='retained-unlock-capture:caller'):
        vm_probe.reproduce_denial(None, object, None, 'request-form', 'kiosk-entry', unlock_capture=True)


def test_unlock_capture_window_must_span_recipient_proofs_and_desktop_boundary(tmp_path):
    from retained_unlock_capture import Capture
    capture = Capture(None, None, tmp_path)
    with pytest.raises(runner.Error, match='capture:window-ended'):
        capture.require_active()
    capture.ready.set()
    capture.rows.append({'event': 'ready'})
    capture.require_active()
    capture.rows.append({'event': 'finished'})
    with pytest.raises(runner.Error, match='capture:window-ended'):
        capture.require_active()
    capture.rows.pop()
    capture.done.set()
    with pytest.raises(runner.Error, match='capture:window-ended'):
        capture.require_active()


@pytest.mark.parametrize('fault', [None, 'duplicate', 'foreign', 'bad-state', 'deadline'])
def test_unlock_capture_baseline_reads_roles_and_states_without_names_or_password_text(monkeypatch, fault):
    import retained_unlock_capture as capture
    from public_atspi import ROOT
    native = SimpleNamespace(Role=SimpleNamespace(DIALOG=10, ALERT=11, PASSWORD_TEXT=12),
        StateType=SimpleNamespace(MODAL=1, SHOWING=2, VISIBLE=3))
    def call(owner, path, interface, method):
        assert owner == ':1.7' and interface == 'org.a11y.atspi.Accessible'
        assert method in ('GetRole', 'GetState', 'GetChildren')
        if method == 'GetRole':
            return {ROOT: 0, '/dialog': 10, '/password': 12}[path]
        if method == 'GetState':
            return [0] if fault == 'bad-state' else [14 if path == '/dialog' else 12, 0]
        return ({ROOT: [(':9.9' if fault == 'foreign' else ':1.7', '/dialog')],
                 '/dialog': [(':1.7', ROOT if fault == 'duplicate' else '/password')],
                 '/password': []}[path])
    api = SimpleNamespace(call=Mock(side_effect=call))
    if fault == 'deadline':
        monkeypatch.setattr(capture.time, 'monotonic', Mock(side_effect=[0, 11]))
    if fault:
        with pytest.raises(RuntimeError, match='capture:baseline'):
            capture.shell_baseline(api, ':1.7', native)
    else:
        roles, interesting = capture.shell_baseline(api, ':1.7', native)
        assert roles == {ROOT: 'other', '/dialog': 'dialog', '/password': 'password'}
        assert [item['role'] for item in interesting] == ['dialog', 'password']
        assert interesting[0] == {'role': 'dialog', 'modal': True, 'visible': True,
            'showing': True, 'source_sha256': hashlib.sha256(b':1.7/dialog').hexdigest()}
        assert interesting[1]['modal'] is False


@pytest.mark.parametrize('observer_failed', [False, True])
@pytest.mark.parametrize('fault', ['journal', 'before-guard', 'after-guard'])
def test_native_log_capture_failure_preserves_observer_failure_and_never_claims_prompt(
        tmp_path, monkeypatch, capsys, observer_failed, fault):
    from contextlib import nullcontext
    import vm_probe
    import ui_observations
    import qualification_storage
    observer = SimpleNamespace(observe=Mock(side_effect=(runner.Error('observer-refusal')
        if observer_failed else lambda operation: {'operation': operation, 'outcome': 'passed'})))
    monkeypatch.setattr(ui_observations, 'UiObservations', Mock(return_value=observer))
    transport = SimpleNamespace(call=Mock(return_value=b'{"uid":1005,"since":100}'))
    monkeypatch.setattr(vm_probe, 'connect', Mock(return_value=transport))
    monkeypatch.setattr(qualification_storage, 'recovery_session', recovery_context)
    monkeypatch.setattr(qualification_storage, 'allocate', lambda *_args, **_kwargs: str(tmp_path))
    capture = Mock(side_effect=runner.Error('journal-refusal') if fault == 'journal' else None)
    monkeypatch.setattr(vm_probe, 'capture_kiosk_native_log', capture)
    guarded = 1 if observer_failed else 2
    guards = [None] * guarded + ([runner.Error('capture-guard')] if fault == 'before-guard'
        else [None, runner.Error('capture-guard')] if fault == 'after-guard' else [None, None])
    lease = SimpleNamespace(commands=SimpleNamespace(directory=None), guard=Mock(side_effect=guards))
    with pytest.raises(runner.Error, match='observer-refusal' if observer_failed else
                       'journal-refusal' if fault == 'journal' else 'capture-guard'):
        vm_probe.probe_kiosk_approval(lease)
    assert observer.observe.call_count == guarded
    assert capture.call_count == (0 if fault == 'before-guard' else 1)
    assert json.loads((tmp_path / 'native-log-result.json').read_text())['outcome'] == 'refused'
    assert (tmp_path / 'observed.json').is_file()
    assert 'prompt retained' not in capsys.readouterr().out


def test_native_log_capture_filters_exact_agent_and_glycin_labels(tmp_path):
    import vm_probe
    unit = 'oh-no-parent-control-polkit-agent.service'
    def record(message, **fields):
        return dict(__REALTIME_TIMESTAMP='100000001', MESSAGE=message, **fields)
    rows = [record(list(b'\x1b[32mloader Frame complete'), _SYSTEMD_USER_UNIT=unit, _UID='1005'),
        record('other user', _SYSTEMD_USER_UNIT=unit, _UID='1000'),
        record('unrelated unit', _SYSTEMD_USER_UNIT='other.service', _UID='1005'),
        record('scontext=system_u:system_r:onpc_kiosk_glycin_bwrap_t:s0', _TRANSPORT='kernel'),
        record('scontext=system_u:system_r:onpc_kiosk_glycin_t:s0', _TRANSPORT='audit'),
        record('profile="onpc-kiosk-glycin-bwrap"', _TRANSPORT='kernel'),
        record('profile="onpc-kiosk-glycin"', _TRANSPORT='kernel'),
        record('profile="onpc-kiosk-glycin-unknown"', _TRANSPORT='kernel'),
        record('scontext=system_u:system_r:onpc_kiosk_glycin_unknown_t:s0', _TRANSPORT='audit'),
        record('scontext=system_u:system_r:init_t:s0', _TRANSPORT='kernel')]
    transport = SimpleNamespace(call=Mock(return_value=b'\n'.join(
        json.dumps(row).encode() for row in rows)))
    vm_probe.capture_kiosk_native_log(transport, tmp_path, uid=1005, since=100)
    saved = json.loads((tmp_path / 'native-log.json').read_text())
    assert [row['source'] for row in saved] == ['agent'] + ['kernel-audit'] * 4
    assert saved[0]['message'] == '\x1b[32mloader Frame complete'
    assert json.loads((tmp_path / 'native-log-result.json').read_text())['records'] == 5
    argv = transport.call.call_args_list[0].args[0]
    assert '_UID=1005' in argv and '_SYSTEMD_USER_UNIT=' + unit in argv
    assert '--since=@100' in argv and '--lines=256' in argv
    assert '--quiet' in argv
    assert not any(item.startswith('--grep=') for item in transport.call.call_args.args[0])
    assert transport.call.call_count == 2
    assert transport.call.call_args.kwargs == {'timeout': 30}


@pytest.mark.parametrize('fault', ['oversize', 'malformed', 'old', 'long-message', 'count', 'bad-bytes', 'invalid-utf8'])
def test_native_log_capture_rejects_unbounded_or_stale_output(tmp_path, fault):
    import vm_probe
    row = dict(__REALTIME_TIMESTAMP='100000001', MESSAGE='decoded', _UID='1005',
               _SYSTEMD_USER_UNIT='oh-no-parent-control-polkit-agent.service')
    if fault == 'old':
        row['__REALTIME_TIMESTAMP'] = '99999999'
    elif fault == 'long-message':
        row['MESSAGE'] = 'x' * 8193
    elif fault == 'bad-bytes':
        row['MESSAGE'] = [256]
    elif fault == 'invalid-utf8':
        row['MESSAGE'] = [255]
    raw = b'x' * (1024 * 1024 + 1) if fault == 'oversize' else b'{' if fault == 'malformed' else (
        b'\n'.join([json.dumps(row).encode()] * (257 if fault == 'count' else 1)))
    transport = SimpleNamespace(call=Mock(return_value=raw))
    with pytest.raises((runner.Error, ValueError)):
        vm_probe.capture_kiosk_native_log(transport, tmp_path, uid=1005, since=100)
    assert not (tmp_path / 'native-log-result.json').exists()


def test_native_capture_cannot_be_enabled_for_other_reproduction_routes():
    import vm_probe
    with pytest.raises(runner.Error, match='kiosk-native-log:caller'):
        vm_probe.reproduce_denial(None, object, None, 'request-form', 'kiosk-entry', native_log=True)


@pytest.mark.parametrize('refused', [False, True])
@pytest.mark.parametrize('cleanup_complete', [False, True])
def test_preferences_boundary_diagnostic_runs_once_without_acceptance_and_requires_worker_cleanup(
        tmp_path, monkeypatch, refused, cleanup_complete):
    from contextlib import nullcontext
    import vm_probe
    import fixture_credentials
    import e2e_worker
    import qualification_storage
    import ui_observations
    from kiosk_preferences_confinement import PLAN
    monkeypatch.setattr(qualification_storage, 'recovery_session', recovery_context)
    monkeypatch.setattr(qualification_storage, 'allocate', lambda *_args, **_kwargs: str(tmp_path))
    monkeypatch.setattr(fixture_credentials, 'FixtureCredentials', Mock())
    monkeypatch.setattr(vm_probe, 'connect', Mock(return_value=object()))
    result = {'operation': 'kiosk-preferences-confinement', 'outcome': 'passed'}
    observer = SimpleNamespace(observe=Mock(
        side_effect=RuntimeError('private diagnostic refusal') if refused else None,
        return_value=result))
    monkeypatch.setattr(ui_observations, 'UiObservations', Mock(return_value=observer))
    boundary = 'preferences-confined'
    prefix = PLAN.stages[:PLAN.stages.index(boundary)]
    class Journey:
        def __init__(self, context, progress, *, plan):
            self.plan = plan
            self.failed = False
            self.steps = [{'stage': stage} for stage in prefix]
        def step(self, guard):
            pytest.fail('diagnostic must stop before the acceptance stage')
    def run(directory, lease, ledger, **kwargs):
        assert kwargs['maintenance'] is True
        (directory / (boundary + '.request.json')).write_text(json.dumps(
            {'stage': boundary, 'screenshot': None}))
        assert kwargs['guarded_observe'](Mock()) is True
        kwargs['validate']()
        assert not (directory / (boundary + '.reply.json')).exists()
        observer.observe.assert_called_once_with('kiosk-preferences-confinement')
        return {'worker_stopped': cleanup_complete, 'callback_closed': cleanup_complete}
    monkeypatch.setattr(e2e_worker, 'run_distribution', run)
    lease = SimpleNamespace(commands=SimpleNamespace(directory=None), guard=Mock())
    arguments = (lease, Journey, PLAN, boundary, 'kiosk-preferences')
    if cleanup_complete:
        vm_probe.reproduce_denial(*arguments,
            boundary_operation='kiosk-preferences-confinement')
        lease.guard.assert_called_once_with()
    else:
        with pytest.raises(runner.Error, match='diagnosis:cleanup-incomplete'):
            vm_probe.reproduce_denial(*arguments,
                boundary_operation='kiosk-preferences-confinement')
        lease.guard.assert_not_called()
    retained = json.loads((tmp_path / 'boundary-observation.json').read_text())
    assert retained == ({'outcome': 'refused', 'error_type': 'RuntimeError'} if refused else result)


@pytest.mark.parametrize('worker_stopped,callback_closed', [
    (True, True), (False, True), (True, False)])
@pytest.mark.parametrize('ssh_status', ['success', 255, 0, -9, None, True, -65, 256, '255', 'missing'])
def test_baseline_app_effects_boundary_keeps_scene_without_reply_and_requires_cleanup(
        tmp_path, monkeypatch, capsys, worker_stopped, callback_closed, ssh_status):
    from contextlib import nullcontext
    import vm_probe
    import baseline_app_effects
    import fixture_credentials
    import e2e_worker
    import qualification_storage
    import provenance
    import native_fixtures
    import ui_observations
    import tools.test_storage as storage
    plan = baseline_app_effects.PLAN
    boundary = 'allowed-use-command'
    prefix = plan.stages[:plan.stages.index(boundary)]
    monkeypatch.setattr(qualification_storage, 'recovery_session', recovery_context)
    monkeypatch.setattr(qualification_storage, 'allocate', lambda *_args, **_kwargs: str(tmp_path))
    monkeypatch.setattr(fixture_credentials, 'FixtureCredentials', Mock())
    assets = Mock()
    monkeypatch.setattr(storage, 'named_input', Mock(return_value=assets))
    source = object()
    artifact_source = Mock(return_value=source)
    monkeypatch.setattr(vm_probe.system, 'artifact_source', artifact_source)
    stage_assets = Mock(side_effect=lambda source, staged, commands: staged.mkdir())
    monkeypatch.setattr(vm_probe.system, 'stage_assets', stage_assets)
    preflight = Mock()
    monkeypatch.setattr(provenance, 'preflight_source', preflight)
    names = native_fixtures.sources()
    verified = SimpleNamespace(
        source_files={'tests/e2e/baseline_app_effects.py': 'a' * 64},
        asset_files={name: f'{index:064x}' for index, name in enumerate(names)},
        recheck=Mock())
    capture_inputs = Mock(return_value=verified)
    monkeypatch.setattr(provenance, 'VerifiedInputs', capture_inputs)
    receipt = {'files': {name: verified.asset_files[name] for name in names},
               'launchers': [native_fixtures.desktop_id(asset[0])
                             for asset in native_fixtures.ASSETS]}
    transport = SimpleNamespace(config={'run': 'owned-attempt'}, guard=Mock(), call=Mock(
        side_effect=[(json.dumps(value, sort_keys=True) + '\n').encode()
                     for value in ({'wrong_entry_refused': True}, receipt, receipt)]))
    if ssh_status != 'missing':
        transport.commands = SimpleNamespace(last_returncode=ssh_status)
    monkeypatch.setattr(vm_probe, 'connect', Mock(return_value=transport))
    observed = {'operation': 'overlay-native-allowed-command-launch', 'outcome': 'passed'}
    observer = SimpleNamespace(observe=Mock(return_value=observed,
        side_effect=None if ssh_status == 'success' else runner.CommandError('private uncertain SSH input')))
    monkeypatch.setattr(ui_observations, 'UiObservations', Mock(return_value=observer))
    journeys = []
    class Journey(baseline_app_effects.BaselineAppEffectsJourney):
        def __init__(self, context, progress, *, plan):
            super().__init__(context, progress, plan=plan)
            self.transport = transport
            self.steps = [{'stage': stage} for stage in prefix]
            journeys.append(self)
        def step(self, guard):
            pytest.fail('the uncertain native launch must never advance or replay')
    monkeypatch.setattr(baseline_app_effects, 'BaselineAppEffectsJourney', Journey)
    def run(directory, lease, ledger, **kwargs):
        assert kwargs['maintenance'] is True
        assert kwargs['timeout'] == 900
        assert kwargs['expected_inputs'] == verified.source_files
        capture_inputs.assert_called_once_with(lease=lease, assets=directory / 'input')
        stage_assets.assert_called_once_with(source, directory / 'input', lease.commands)
        artifact_source.assert_called_once_with(assets)
        preflight.assert_called_once_with(directory / 'input')
        journey = journeys[0]
        assert journey.context.verified is verified
        # Keep the real fixture action/controller/command chain. Only the guest
        # transport and provenance hashing are doubles in this private unit test.
        fixture_guard = Mock()
        assert journey.actions[plan.stage_actions['installed-greeter']](
            journey, fixture_guard) == {'wrong_entry_refused': True}
        assert journey.actions[plan.stage_actions['desktop']](journey, fixture_guard) == {
            'verified': len(native_fixtures.ASSETS), 'verified_files': len(names),
            'independent_readback': True}
        assert verified.recheck.call_count == 6
        assert [call.args[0][3] for call in transport.call.call_args_list] == ['refuse', 'read', 'read']
        (directory / (boundary + '.request.json')).write_text(json.dumps(
            {'stage': boundary, 'screenshot': None}))
        def guard_probe():
            if observer.observe.called and hasattr(transport, 'commands'):
                transport.commands.last_returncode = 0
        guard = Mock(side_effect=guard_probe)
        assert kwargs['guarded_observe'](guard) is True
        assert guard.call_count == 2
        kwargs['validate']()
        observer.observe.assert_called_once_with('overlay-native-allowed-command-launch')
        assert [row['stage'] for row in journey.steps] == list(prefix)
        assert not (directory / (boundary + '.reply.json')).exists()
        assert not (directory / (boundary + '.reply.tmp')).exists()
        retained = json.loads((directory / 'boundary-observation.json').read_text())
        expected = observed if ssh_status == 'success' else {
            'outcome': 'refused', 'error_type': 'CommandError'}
        if ssh_status != 'success' and type(ssh_status) is int and -64 <= ssh_status <= 255:
            expected['ssh_returncode'] = ssh_status
        assert retained == expected
        return {'worker_stopped': worker_stopped, 'callback_closed': callback_closed}
    monkeypatch.setattr(e2e_worker, 'run_distribution', run)
    lease = SimpleNamespace(commands=SimpleNamespace(directory=None), guard=Mock())
    if worker_stopped and callback_closed:
        vm_probe.reproduce_baseline_app_effects(lease)
        lease.guard.assert_called_once_with()
    else:
        with pytest.raises(runner.Error, match='diagnosis:cleanup-incomplete'):
            vm_probe.reproduce_baseline_app_effects(lease)
        lease.guard.assert_not_called()
    output = capsys.readouterr()
    assert 'private uncertain SSH input' not in output.out + output.err
    if worker_stopped and callback_closed:
        assert 'scene retained; evidence=' + str(tmp_path) in output.out


@pytest.mark.parametrize('fault', [None, 'uri', 'uuid', 'name'])
def test_snapshot_inventory_uses_only_pinned_read_only_connection(monkeypatch, capsys, fault):
    api = Mock()
    connection = api.openReadOnly.return_value
    domain = connection.lookupByUUIDString.return_value
    connection.getURI.return_value = 'qemu:///system' if fault != 'uri' else 'qemu:///session'
    domain.UUIDString.return_value = UUID if fault != 'uuid' else 'f' * 36
    domain.name.return_value = runner.baseline.DOMAIN if fault != 'name' else 'other'
    snapshot = Mock()
    snapshot.getName.return_value = '1 - Clean'
    snapshot.getXMLDesc.return_value = '<domainsnapshot/>'
    domain.listAllSnapshots.return_value = [snapshot]
    monkeypatch.setattr(control.importlib, 'import_module', lambda name: api)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.os, 'getegid', lambda: 0)
    monkeypatch.setattr(control.os, 'umask', lambda value: 0)
    assert control.main([*VM_ARGS, '--expected-uuid', UUID, 'snapshots']) == (2 if fault else 0)
    connection.lookupByUUIDString.assert_called_once_with(UUID)
    connection.close.assert_called_once()
    api.open.assert_not_called()
    api.virEventRegisterDefaultImpl.assert_not_called()
    domain.revertToSnapshot.assert_not_called()
    if fault:
        domain.listAllSnapshots.assert_not_called()
    else:
        assert json.loads(capsys.readouterr().out) == [{'name': '1 - Clean', 'xml': '<domainsnapshot/>'}]


def test_root_guest_dispatch_keeps_arbitrary_command_inside_the_fixed_controller():
    root = Path(__file__).resolve().parents[2]
    dispatch = runpy.run_path(str(root / 'tools/onpc-test-runner'))['selection']
    dispatch.__globals__['VM_UUIDS'] = {vm_name(): UUID}
    guest = ['sh', '-c', 'journalctl; id -u', '--vm', 'unknown-vm', '--help', '--list']
    command = dispatch(root, ['vm', 'exec', *VM_ARGS, '--timeout', '600', '--', *guest])
    assert command == ['/usr/bin/python3', '-B', str(root / 'tests/integration/vm_control.py'),
                       *VM_ARGS, '--expected-uuid', UUID, 'exec', '--timeout', '600', '--', *guest]
    with pytest.raises(ValueError, match='--vm'):
        dispatch(root, ['vm', 'exec', '--', *guest])


@pytest.mark.parametrize('fault,scene',
    [(fault, 'lock') for fault in [None, 'failed', 'missing-history', 'advanced',
                                  'wrong-stage', 'screenshot', 'symlink', 'oversized']] +
    [(None, scene) for scene in ['retained-entry', 'transfer-refusal', 'remembered-return',
                                 'riley-native-grid', 'retained-app-visits', 'revoke-cancel',
                                 'countdown-minutes', 'countdown-resume', 'kiosk-entry',
                                 'kiosk-approval', 'kiosk-preferences', 'baseline-app-effects']])
def test_reproduction_retains_only_complete_declared_history(tmp_path, fault, scene):
    from vm_probe import validate_boundary
    from desktop_session import CHILD_DENIAL_PLAN, CHILD_UNLOCK_PLAN
    from retained_entry import PLAN
    from choices_overlay_to_kiosk import PLAN as TRANSFER_PLAN
    from remembered_choices import DIAGNOSTIC_PLAN as REMEMBERED_PLAN
    from riley_native_grid import PLAN as RILEY_GRID_PLAN
    from retained_app_visits import PLAN as RETAINED_APP_PLAN
    from time_explanation import REVOKE_PLAN
    from countdown_qualification import MINUTE_PLAN
    from kiosk_entry import PLAN as KIOSK_PLAN
    from kiosk_approved_flow import PLAN as KIOSK_APPROVAL_PLAN
    from kiosk_preferences_confinement import PLAN as KIOSK_PREFERENCES_PLAN
    from baseline_app_effects import PLAN as BASELINE_APP_EFFECTS_PLAN
    plan, boundary, previous = {
        'lock': (CHILD_DENIAL_PLAN, 'time-denied', 'reveal-ready'),
        'retained-entry': (PLAN, 'riley-restricted-curtain', 'riley-restricted-entry-guard'),
        'transfer-refusal': (TRANSFER_PLAN, 'riley-refused', 'riley-default'),
        'remembered-return': (REMEMBERED_PLAN, 'jordan-return-entry-desktop',
                              'jordan-return-entry-standard-recipient-rechecked'),
        'riley-native-grid': (RILEY_GRID_PLAN, 'repeat-refusals', 'repeat-search-entered'),
        'retained-app-visits': (RETAINED_APP_PLAN, 'riley-activity-command', 'riley-activity-desktop'),
        'revoke-cancel': (REVOKE_PLAN, 'second-balances', 'second-cancel'),
        'countdown-minutes': (MINUTE_PLAN, 'minute-progression', 'fresh-desktop'),
        'countdown-resume': (CHILD_UNLOCK_PLAN, 'returned-activity', 'unlock-desktop'),
        'kiosk-entry': (KIOSK_PLAN, 'request-form', 'station-branch'),
        'kiosk-approval': (KIOSK_APPROVAL_PLAN, 'approval-qualified', 'approval-open'),
        'kiosk-preferences': (KIOSK_PREFERENCES_PLAN, 'preferences-confined', 'open-estimate'),
        'baseline-app-effects': (BASELINE_APP_EFFECTS_PLAN, 'allowed-use-command', 'allowed-use-desktop'),
    }[scene]
    stages = list(plan.stages)
    prefix = stages[:stages.index(boundary)]
    assert prefix[-1] == previous
    assert ('lock-recipient-qualified' in prefix) == (scene == 'countdown-resume')
    if fault == 'missing-history':
        prefix.remove(previous)
    elif fault == 'advanced':
        prefix.append(boundary)
    journey = SimpleNamespace(plan=plan, failed=fault == 'failed',
                              steps=[{'stage': stage} for stage in prefix])
    request = tmp_path / (boundary + '.request.json')
    request.write_text(json.dumps({'stage': 'curtain' if fault == 'wrong-stage' else boundary,
                                  'screenshot': 'private' if fault == 'screenshot' else None}))
    if fault == 'symlink':
        request.rename(tmp_path / 'original')
        request.symlink_to(tmp_path / 'original')
    elif fault == 'oversized':
        request.write_text(' ' * 1025)
    if fault:
        with pytest.raises(runner.Error, match='diagnosis:'):
            validate_boundary(journey, tmp_path, boundary)
    else:
        validate_boundary(journey, tmp_path, boundary)


def test_public_probe_launcher_keeps_host_selector_before_guest_arguments(monkeypatch):
    import dev_privileges
    import sys
    root = Path(__file__).resolve().parents[2]
    guest = ['printf', '--vm', 'unknown-vm', '--help', '--list']
    launch = Mock()
    monkeypatch.setattr(dev_privileges, 'launch', launch)
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(sys, 'argv', [str(root / 'tools/test-vm'), *VM_ARGS, 'exec', '--', *guest])
    runpy.run_path(str(root / 'tools/test-vm'), run_name='__main__')
    launch.assert_called_once_with('/usr/local/libexec/onpc-test-runner',
                                  ['vm', *VM_ARGS, 'exec', '--', *guest])


def test_probe_input_is_opened_unprivileged_and_not_forwarded_as_a_host_path(tmp_path):
    source = tmp_path / 'payload.rpm'
    source.write_bytes(b'RPM\0payload')
    root = Path(__file__).resolve().parents[2]
    prepare = runpy.run_path(str(root / 'tools/test-vm'))['input_arguments']
    guest = ['cat', '--input-file', '/guest-only']
    args, fd = prepare(['exec', '--input-file', str(source), '--', *guest])
    try:
        assert args == ['exec', '--stdin', '--', *guest]
        assert os.read(fd, 100) == b'RPM\0payload'
        assert str(source) not in args
    finally:
        os.close(fd)


@pytest.mark.parametrize('fault', ['symlink', 'directory', 'fifo', 'oversize', 'missing', 'wrong-action'])
def test_probe_input_refuses_invalid_files_and_actions(tmp_path, fault):
    root = Path(__file__).resolve().parents[2]
    prepare = runpy.run_path(str(root / 'tools/test-vm'))['input_arguments']
    source = tmp_path / 'payload'
    if fault == 'symlink':
        source.symlink_to(tmp_path)
    elif fault == 'directory':
        source.mkdir()
    elif fault == 'fifo':
        os.mkfifo(source)
    elif fault == 'oversize':
        with source.open('wb') as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
    args = ['status' if fault == 'wrong-action' else 'exec', '--input-file', str(source), '--', 'cat']
    with pytest.raises(ValueError, match='vm-probe:'):
        prepare(args)


def test_dispatcher_passes_input_marker_without_a_privileged_host_path():
    root = Path(__file__).resolve().parents[2]
    dispatch = runpy.run_path(str(root / 'tools/onpc-test-runner'))['selection']
    dispatch.__globals__['VM_UUIDS'] = {vm_name(): UUID}
    command = dispatch(root, ['vm', 'exec', *VM_ARGS, '--stdin', '--', 'cat'])
    assert command[-3:] == ['--stdin', '--', 'cat']


@pytest.mark.parametrize('args', [[], ['id'], ['--'], ['--host', 'other', '--', 'id']])
def test_root_guest_dispatch_refuses_invalid_host_controls(args):
    root = Path(__file__).resolve().parents[2]
    dispatch = runpy.run_path(str(root / 'tools/onpc-test-runner'))['selection']
    with pytest.raises(ValueError, match='vm-probe:'):
        dispatch(root, ['vm', 'exec', *VM_ARGS, *args])


def probe_snapshot(held, current):
    """Current snapshot identity double, backed only by a private lease fixture."""
    tree = ET.Element('domainsnapshot')
    ET.SubElement(tree, 'state').text = 'running'
    ET.SubElement(tree, 'memory', snapshot='internal')
    ET.SubElement(tree, 'description').text = json.dumps({'baseline_sha256': held.state['baseline_sha256']})
    tree.append(ET.fromstring(current['xml']))
    snapshot = Mock()
    snapshot.getName.return_value = 'onpc-v9.8.7'
    snapshot.getXMLDesc.side_effect = lambda _: ET.tostring(tree, encoding='unicode')
    held.source.domain.snapshotCurrent.return_value = snapshot
    record = {'run': held.state['run'], 'private_key': 'private-key-canary'}
    return tree, snapshot, record


@pytest.mark.parametrize('status', [0, 1, 127, 255])
@pytest.mark.parametrize('input_stream', [False, True])
@pytest.mark.parametrize('maintenance', [False, True])
def test_root_probe_preserves_guest_state_and_exit_status(lease_rig, monkeypatch, capsys, status, input_stream, maintenance):
    import online_snapshot
    import vm_probe
    lease, current = lease_rig
    start(lease)
    held = reopened(lease)
    control.resume(held)
    held.commands.directory = lease.directory / 'probe-scratch'
    held.commands.directory.mkdir()
    _, _, record = probe_snapshot(held, current)
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=record))
    monkeypatch.setattr(online_snapshot, 'load_maintenance', Mock(
        return_value=record if maintenance else None))
    monkeypatch.setattr(vm_probe.system, 'address', Mock(return_value='192.168.122.20'))
    transport = Mock()
    if input_stream:
        import io
        from types import SimpleNamespace
        original_stat, original_seek = os.fstat, os.lseek
        monkeypatch.setattr(vm_probe.os, 'fstat', lambda fd: SimpleNamespace(st_mode=0o100600, st_size=7)
                            if fd == 0 else original_stat(fd))
        monkeypatch.setattr(vm_probe.os, 'lseek', lambda fd, offset, whence: 0
                            if fd == 0 else original_seek(fd, offset, whence))
        monkeypatch.setattr(vm_probe.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(b'payload')))
    def run(command, **kwargs):
        assert command == ['journalctl', '--no-pager']
        assert kwargs['check'] is False and kwargs['timeout'] == 120
        assert kwargs.get('input') == (b'payload' if input_stream else None)
        kwargs['on_stream'](b'guest stdout\n', 'stdout')
        kwargs['on_stream'](b'guest stderr\n', 'stderr')
        transport.commands.last_returncode = status
    transport.call.side_effect = run
    connect = Mock(return_value=transport)
    monkeypatch.setattr(online_snapshot, 'connect_saved_transport', connect)
    journal, owner = held.journal.read_bytes(), (held.directory / 'vm-control.json').read_bytes()
    restores = held.source.domain.revertToSnapshot.call_count
    guard = held.guard
    def checked_guard():
        guard()
        transport.commands.last_returncode = 0
    held.guard = checked_guard
    try:
        assert vm_probe.execute(held, ['journalctl', '--no-pager'], 120, input_stream=input_stream) == status
        connect.assert_called_once_with(held, held.commands.directory, record, '192.168.122.20')
        if maintenance:
            held.source.domain.snapshotCurrent.assert_not_called()
        assert held.journal.read_bytes() == journal
        assert (held.directory / 'vm-control.json').read_bytes() == owner
        assert held.source.domain.revertToSnapshot.call_count == restores
        assert current['id'] == 71
        out = capsys.readouterr()
        assert 'guest stdout' in out.out and 'guest stderr' in out.err
        assert 'private-key-canary' not in out.out + out.err
    finally:
        held.release()


@pytest.mark.parametrize('fault', ['credentials', 'name', 'memory', 'uuid', 'run', 'baseline'])
def test_root_probe_refuses_unbound_snapshot_credentials_before_connecting(lease_rig, monkeypatch, fault):
    import online_snapshot
    import vm_probe
    lease, current = lease_rig
    start(lease)
    held = reopened(lease)
    control.resume(held)
    tree, snapshot, record = probe_snapshot(held, current)
    if fault == 'credentials':
        record = None
    elif fault == 'name':
        snapshot.getName.return_value = 'onpc_baseline'
    elif fault == 'memory':
        tree.find('memory').set('snapshot', 'no')
    elif fault == 'uuid':
        tree.find('domain/uuid').text = '0' * 36
    elif fault == 'run':
        record['run'] = 'f' * 32
    elif fault == 'baseline':
        tree.find('description').text = json.dumps({'baseline_sha256': 'f' * 64})
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=record))
    connect = Mock()
    monkeypatch.setattr(online_snapshot, 'connect_saved_transport', connect)
    address = Mock()
    monkeypatch.setattr(vm_probe.system, 'address', address)
    journal = held.journal.read_bytes()
    restores = held.source.domain.revertToSnapshot.call_count
    try:
        with pytest.raises(RuntimeError):
            vm_probe.execute(held, ['id', '-u'], 120)
        connect.assert_not_called()
        address.assert_not_called()
        assert held.journal.read_bytes() == journal
        assert held.source.domain.revertToSnapshot.call_count == restores
    finally:
        held.release()


@pytest.mark.parametrize('fault', ['pipe', 'oversize', 'offset', 'changed'])
def test_root_probe_refuses_invalid_input_before_ssh(lease_rig, monkeypatch, fault):
    import io
    from types import SimpleNamespace
    import online_snapshot
    import vm_probe
    lease, current = lease_rig
    start(lease)
    held = reopened(lease)
    control.resume(held)
    _, _, record = probe_snapshot(held, current)
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=record))
    monkeypatch.setattr(vm_probe.system, 'address', Mock(return_value='192.168.122.20'))
    connect = Mock()
    monkeypatch.setattr(online_snapshot, 'connect_saved_transport', connect)
    original_stat, original_seek = os.fstat, os.lseek
    info = SimpleNamespace(st_mode=0o010600 if fault == 'pipe' else 0o100600,
                           st_size=64 * 1024 * 1024 + 1 if fault == 'oversize' else 7)
    monkeypatch.setattr(vm_probe.os, 'fstat', lambda fd: info if fd == 0 else original_stat(fd))
    monkeypatch.setattr(vm_probe.os, 'lseek', lambda fd, offset, whence:
                        (1 if fault == 'offset' else 0) if fd == 0 else original_seek(fd, offset, whence))
    monkeypatch.setattr(vm_probe.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(b'short')))
    journal = held.journal.read_bytes()
    try:
        with pytest.raises(RuntimeError, match='vm-probe:'):
            vm_probe.execute(held, ['cat'], 120, input_stream=True)
        connect.assert_not_called()
        assert held.journal.read_bytes() == journal
    finally:
        held.release()


@pytest.mark.parametrize('fault', ['owner', 'busy', 'instance'])
def test_root_probe_refuses_foreign_or_active_controller_before_ssh(lease_rig, monkeypatch, fault):
    import vm_probe
    lease, current = lease_rig
    if fault == 'busy':
        lease.view.graphics_type = 'vnc'
        with patch('vm_probe.prepare_maintenance_transport'):
            control.operate(lease, 'start', [])
    else:
        start(lease)
        if fault == 'owner':
            (lease.directory / 'vm-control.json').write_text('{}')
        else:
            current['id'] += 1
    execute = Mock()
    monkeypatch.setattr(vm_probe, 'execute', execute)
    held = reopened(lease)
    try:
        with pytest.raises(RuntimeError):
            control.resume(held)
        execute.assert_not_called()
    finally:
        held.release()
        lease.release()


@pytest.mark.parametrize('argv', [
    ['vm', 'rename'], ['vm', 'rename', '--new-name', '../another'],
    ['vm', 'rename', '--new-name', '-flag'],
    ['vm', 'start', '--new-name', 'another'],
    ['vm', 'rename', '1', '--new-name', 'another'],
])
def test_dispatcher_refuses_invalid_rename_destinations(argv):
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    dispatcher['selection'].__globals__['VM_UUIDS'] = {vm_name(): UUID}
    with pytest.raises(ValueError):
        dispatcher['selection'](Path(__file__).resolve().parents[2], [*argv, *VM_ARGS])


def test_dispatcher_rename_keeps_uuid_pin_and_only_accepts_destination_label():
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    dispatcher['selection'].__globals__['VM_UUIDS'] = {vm_name(): UUID}
    assert dispatcher['selection'](root, ['vm', 'rename', '--new-name', 'custom-Ubuntu26.04', *VM_ARGS])[3:] == [
        *VM_ARGS, '--expected-uuid', UUID, 'rename', '--new-name', 'custom-Ubuntu26.04']


def rename_rig(lease, current, monkeypatch):
    """Private named and legacy leases; no real libvirt access."""
    import vm_config
    root = lease.directory.parent
    (root / '.lock').touch(mode=0o600)
    monkeypatch.setattr(vm_config, 'STATE_ROOT', root)
    monkeypatch.setattr(runner.baseline, 'DOMAIN', runner.baseline.DOMAIN)
    source = lease.source
    source.api.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE = 1
    source.api.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT = 2
    source.domain.UUIDString.return_value = UUID
    source.domain.name.side_effect = lambda: ET.fromstring(current['xml']).findtext('name')
    source.connection.lookupByUUIDString.return_value = source.domain
    snapshots = {runner.baseline.SNAPSHOT: source.baseline_xml,
                 'onpc-v9.9': source.baseline_xml.replace(
                     '<name>' + runner.baseline.SNAPSHOT + '</name>', '<name>onpc-v9.9</name>')}
    def snapshot(name):
        value = Mock()
        value.getName.return_value = name
        value.getXMLDesc.side_effect = lambda *_: snapshots[name]
        return value
    source.domain.listAllSnapshots.side_effect = lambda *_: [snapshot(name) for name in snapshots]
    source.domain.snapshotLookupByName.side_effect = lambda name, *_: snapshot(name)
    source.domain.hasCurrentSnapshot.return_value = True
    source.domain.snapshotCurrent.return_value = snapshot(runner.baseline.SNAPSHOT)
    def renamed(name, *_):
        tree = ET.fromstring(current['xml'])
        tree.find('name').text = name
        current['xml'] = ET.tostring(tree, encoding='unicode')
    source.domain.rename.side_effect = renamed
    def redefine(xml, flags):
        name = ET.fromstring(xml).findtext('name')
        assert flags & source.api.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE
        snapshots[name] = xml
        source.baseline_xml = snapshots[runner.baseline.SNAPSHOT]
        return snapshot(name)
    source.domain.snapshotCreateXML.side_effect = redefine
    return snapshots, redefine


def test_rename_preserves_disks_uuid_snapshot_contents_and_provenance(lease_rig, monkeypatch):
    lease, current = lease_rig
    snapshots, _ = rename_rig(lease, current, monkeypatch)
    old_name = runner.baseline.DOMAIN
    directory = lease.directory
    identity = directory.stat().st_ino
    original = current['xml']
    originals = snapshots.copy()
    state = (directory / 'phase.json').read_bytes()
    before = {item['path']: Path(item['path']).read_bytes()
              for item in json.loads(state)['source']['chain']}
    try:
        control.rename(lease, 'custom-Ubuntu26.04')
        assert not directory.exists()
        assert lease.directory.name == 'custom-Ubuntu26.04'
        assert lease.directory.stat().st_ino == identity
        assert (lease.directory / 'phase.json').read_bytes() == state
        assert control.same_xml(current['xml'], control.renamed_xml(original, old_name, 'custom-Ubuntu26.04', UUID))
        assert snapshots == originals
        lease.source.domain.snapshotCreateXML.assert_not_called()
        assert all(Path(path).read_bytes() == content for path, content in before.items())
        assert lease.source.domain.ID() == -1
        assert json.loads(next(lease.directory.glob('rename-*.json')).read_bytes())['phase'] == 'complete'
        assert lease.capture.verify_snapshot() == lease.capture.state['proof']
        lease.source.domain.create.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()
        assert lease.source.creations == [lease.capture.description()]
    finally:
        lease.release()


@pytest.mark.parametrize('fault', ['metadata', 'record-uuid', 'record-name', 'missing-record', 'pending'])
def test_historical_snapshot_name_requires_exact_owned_rename_proof(lease_rig, monkeypatch, fault):
    lease, current = lease_rig
    rename_rig(lease, current, monkeypatch)
    try:
        control.rename(lease, 'custom-Ubuntu26.04')
        record_path = next(lease.directory.glob('rename-*.json'))
        record = json.loads(record_path.read_bytes())
        if fault == 'metadata':
            lease.source.baseline_xml += ' '
        elif fault == 'missing-record':
            record_path.rename(lease.directory / 'preserved-record.json')
        else:
            if fault == 'record-uuid':
                record['domain_uuid'] = 'f' * 36
            elif fault == 'record-name':
                record['new_name'] = 'unrelated-vm'
            else:
                record['phase'] = 'requested'
            record_path.write_text(json.dumps(record))
        with pytest.raises(runner.Error, match='domain-identity'):
            lease.capture.verify_snapshot()
        lease.source.domain.snapshotCreateXML.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()
    finally:
        lease.release()


@pytest.mark.parametrize('fault', ['running', 'busy', 'destination', 'snapshot-uuid', 'pending'])
def test_rename_refusals_leave_domain_snapshots_and_provenance_untouched(lease_rig, monkeypatch, fault):
    import fcntl
    lease, current = lease_rig
    snapshots, _ = rename_rig(lease, current, monkeypatch)
    destination = lease.directory.parent / 'custom-Ubuntu26.04'
    if fault == 'busy':
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        import threading
        started = threading.Event()
        original, originals = current['xml'], snapshots.copy()
        def execute():
            started.set()
            control.rename(lease, destination.name)
        try:
            with ThreadPoolExecutor(max_workers=1) as worker:
                with lease.capture.lock_path.open('rb') as lock:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    result = worker.submit(execute)
                    assert started.wait(5)
                    with pytest.raises(TimeoutError):
                        result.result(timeout=0.1)
                    assert current['xml'] == original and snapshots == originals
                    lease.source.domain.rename.assert_not_called()
                result.result(timeout=5)
            assert destination.is_dir()
            lease.source.domain.rename.assert_called_once()
        finally:
            lease.release()
        return
    if fault == 'running':
        current['id'], lease.source.off = 71, False
    elif fault == 'destination':
        destination.mkdir()
    elif fault == 'snapshot-uuid':
        snapshots['onpc-v9.9'] = snapshots['onpc-v9.9'].replace(UUID, 'f' * 36)
    elif fault == 'pending':
        (lease.directory / 'rename-previous.json').write_text('{"phase":"requested"}')
        (lease.directory / 'rename-previous.json').chmod(0o600)
    original = current['xml']
    originals = snapshots.copy()
    try:
        with pytest.raises(runner.Error):
            control.rename(lease, destination.name)
        assert current['xml'] == original and snapshots == originals
        assert lease.directory.exists()
        lease.source.domain.rename.assert_not_called()
        lease.source.domain.snapshotCreateXML.assert_not_called()
    finally:
        lease.release()


@pytest.mark.parametrize('fault', ['api', 'snapshot', 'move', 'interrupt'])
def test_rename_failures_roll_back_only_owned_metadata(lease_rig, monkeypatch, fault):
    lease, current = lease_rig
    snapshots, redefine = rename_rig(lease, current, monkeypatch)
    original, originals = current['xml'], snapshots.copy()
    directory = lease.directory
    if fault == 'api':
        rename_api = lease.source.domain.rename.side_effect
        def fail_rename(name, flags):
            if name == 'custom-Ubuntu26.04':
                raise runner.Error('fixture:rename-failed')
            return rename_api(name, flags)
        lease.source.domain.rename.side_effect = fail_rename
    elif fault in ('snapshot', 'interrupt'):
        reads = 0
        list_snapshots = lease.source.domain.listAllSnapshots.side_effect
        def fail_snapshot(*args):
            nonlocal reads
            reads += 1
            if reads == 3:
                raise KeyboardInterrupt() if fault == 'interrupt' else runner.Error('fixture:snapshot-failed')
            return list_snapshots(*args)
        lease.source.domain.listAllSnapshots.side_effect = fail_snapshot
    else:
        monkeypatch.setattr(control.os, 'rename', Mock(side_effect=OSError('fixture:move-failed')))
    try:
        with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else (runner.Error, OSError)):
            control.rename(lease, 'custom-Ubuntu26.04')
        assert control.same_xml(current['xml'], original)
        assert all(control.same_xml(snapshots[name], xml) for name, xml in originals.items())
        assert directory.exists() and lease.directory == directory
        assert json.loads(next(directory.glob('rename-*.json')).read_bytes())['phase'] == 'rolled-back'
        lease.source.domain.create.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()
    finally:
        lease.release()


@pytest.mark.parametrize('status', [0, 1, 130])
@pytest.mark.parametrize('argv', [['vm', 'start'], ['vm', 'stop'],
                                 ['integration', 'check_test_recovery']])
def test_foreground_dispatch_runs_only_owned_operation_without_test_gate(tmp_path, monkeypatch, argv, status):
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    dispatcher['run'].__globals__['selection'] = lambda *args: ['selected-operation']
    monkeypatch.setattr(dispatcher['runpy'], 'run_path', lambda _: {
        'safety_command': lambda root: ['shared-qualified-gate']})
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [])
    caller = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name='fixture',
                             pw_dir=str(tmp_path))
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert calls == [['selected-operation']]
        assert kwargs['env']['PKEXEC_UID'] == str(caller.pw_uid)
        assert 'user' not in kwargs
        return SimpleNamespace(returncode=status)
    monkeypatch.setattr(dispatcher['subprocess'], 'run', execute)
    assert dispatcher['run'](root, [*argv, *VM_ARGS], caller) == status
    assert len(calls) == 1


def test_reset_leaves_vm_off_and_never_creates_snapshot_or_vm(lease_rig):
    lease, _ = lease_rig
    lease.view.graphics_type = 'vnc'
    snapshots = len(lease.source.creations)
    try:
        control.operate(lease, 'reset', [])
    finally:
        lease.release()
    lease.source.domain.create.assert_not_called()
    assert len(lease.source.creations) == snapshots
    assert lease.source.off


@pytest.mark.parametrize('running', [False, True])
@pytest.mark.parametrize('fault', ['expired', 'credentials', 'baseline', 'restore'])
def test_online_resume_refusal_preserves_idle_or_running_ownership(
        lease_rig, monkeypatch, tmp_path, running, fault):
    import online_snapshot
    import prepare_snapshot as controller
    from tools import test_retention
    lease, current = lease_rig
    lease.view.graphics_type = 'vnc'
    if running:
        start(lease)
        previous_journal = lease.journal.read_bytes()
        previous_owner = (lease.directory / 'vm-control.json').read_bytes()
        held = reopened(lease)
    else:
        held = lease
    held.capture.directory_identity = held.capture.private_directory()
    baseline_sha256 = hashlib.sha256(runner.baseline.encode(
        held.capture.read_state())).hexdigest()
    root = ET.Element('domainsnapshot')
    ET.SubElement(root, 'memory', snapshot='internal')
    ET.SubElement(root, 'state').text = 'running'
    ET.SubElement(root, 'creationTime').text = str(int(time.time()) - (
        86401 if fault == 'expired' else 0))
    ET.SubElement(root, 'description').text = json.dumps({
        'baseline_sha256': 'f' * 64 if fault == 'baseline' else baseline_sha256})
    root.append(ET.fromstring(runner.isolated_xml(
        current['xml'], UUID, 'e' * 32, graphics_type='vnc')))
    snapshot = Mock()
    snapshot.getXMLDesc.return_value = ET.tostring(root, encoding='unicode')
    lease.source.domain.snapshotLookupByName.return_value = snapshot
    lease.source.close = Mock()
    monkeypatch.setattr(controller, 'open_source', lambda: (lease.source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock())
    monkeypatch.setattr(controller, 'Commands', lambda: lease.commands)
    monkeypatch.setattr(controller.system, 'Lease', lambda *a, **kw: held)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-v9.8.7')
    monkeypatch.setattr(test_retention, 'allocate', lambda *a, **kw: str(tmp_path))
    monkeypatch.setattr(online_snapshot, 'load', lambda *a: (
        None if fault == 'credentials' else {'run': 'e' * 32}))
    lease.source.domain.revertToSnapshot.reset_mock()
    lease.source.domain.revertToSnapshot.side_effect = runner.Error('fixture:restore-interrupted')
    with pytest.raises(RuntimeError, match={
            'expired': 'expired-or-invalid', 'credentials': 'credentials-missing',
            'baseline': 'baseline-changed', 'restore': 'restore-interrupted'}[fault]):
        controller.resume(UUID)
    assert held.fd is None
    state = json.loads(lease.journal.read_bytes())
    if fault == 'restore':
        assert state['phase'] == 'start-requested' and state['domain_id'] is None
        lease.source.domain.revertToSnapshot.assert_called_once()
        if running:
            assert state['run'] != json.loads(previous_journal)['run']
    else:
        lease.source.domain.revertToSnapshot.assert_not_called()
        if running:
            assert lease.journal.read_bytes() == previous_journal
            assert (lease.directory / 'vm-control.json').read_bytes() == previous_owner
        else:
            assert state['phase'] == 'complete'


@pytest.mark.parametrize('fault', [None, 'instance', 'owner', 'credentials', 'sharing', 'baseline'])
@pytest.mark.parametrize('automatic', [False, True, 'recorded'])
def test_explicit_interrupted_online_recovery_is_bound_and_cleanup_only(
        lease_rig, monkeypatch, fault, automatic):
    import online_snapshot
    lease, current = lease_rig
    start(lease)
    saved_run = lease.state['run']
    tree = ET.Element('domainsnapshot')
    ET.SubElement(tree, 'state').text = 'running'
    ET.SubElement(tree, 'memory', snapshot='internal')
    ET.SubElement(tree, 'description').text = json.dumps({
        'baseline_sha256': lease.state['baseline_sha256'] if fault != 'baseline' else 'f' * 64})
    tree.append(ET.fromstring(current['xml']))
    snapshot = Mock()
    snapshot.getName.return_value = 'onpc-v9.8.7'
    snapshot.getXMLDesc.return_value = ET.tostring(tree, encoding='unicode')
    lease.source.domain.listAllSnapshots.return_value = [snapshot]
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=
        None if fault == 'credentials' else {'run': saved_run}))
    lease.state.update(phase='start-requested', domain_id=None, run='b' * 32)
    if automatic == 'recorded':
        lease.state.update(phase='cleanup-requested', domain_id=72 if fault == 'instance' else 71)
    lease.journal.write_bytes(runner.baseline.encode(lease.state))
    control.save_owner(lease)
    if fault == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    if fault == 'sharing':
        current['xml'] = current['xml'].replace('</devices>', '<channel/></devices>')
    resumed = reopened(lease)
    calls = lease.source.domain.revertToSnapshot.call_count
    def recover():
        if automatic:
            if fault == 'instance' and automatic != 'recorded':
                # The observed instance changes before the exclusive lease is
                # acquired. Automation must retain the recorded refusal.
                first = [True]
                def observed_instance():
                    if first:
                        first.pop()
                        return 72
                    return current['id']
                lease.source.domain.ID.side_effect = observed_instance
            control.recover_preparation(resumed)
        else:
            control.operate(resumed, 'recover-online', [72 if fault == 'instance' else 71])
    try:
        if fault:
            with pytest.raises(RuntimeError):
                recover()
            assert lease.source.domain.revertToSnapshot.call_count == calls
        else:
            recover()
            assert resumed.state['phase'] == 'complete'
            assert lease.source.off
            assert lease.source.domain.revertToSnapshot.call_count == calls + 1
        assert lease.source.domain.create.call_count == 1
    finally:
        resumed.release()


@pytest.mark.parametrize('owner_kind', ['absent', 'stale', 'current', 'malformed'])
def test_explicit_online_recovery_routes_without_adopting_maintenance(
        lease_rig, monkeypatch, owner_kind):
    lease, _ = lease_rig
    lease.__enter__()
    control.save_owner(lease)
    owner_path = lease.directory / 'vm-control.json'
    if owner_kind == 'absent':
        owner_path.unlink()
    elif owner_kind == 'stale':
        owner = json.loads(owner_path.read_bytes())
        owner['run'] = 'e' * 32
        owner_path.write_bytes(runner.baseline.encode(owner))
    elif owner_kind == 'malformed':
        owner_path.write_text('{}')
    lease.release()
    recover = Mock()
    monkeypatch.setattr(lease, 'recover_graphical_cleanup', recover)
    resume = Mock(side_effect=runner.Error('fixture:maintenance-route'))
    monkeypatch.setattr(control, 'resume', resume)
    if owner_kind in ('absent', 'stale'):
        control.operate(lease, 'recover-online', [71])
        recover.assert_called_once_with(recovery_instance=71)
        resume.assert_not_called()
    else:
        with pytest.raises(RuntimeError, match='maintenance-route'):
            control.operate(lease, 'recover-online', [71])
        recover.assert_not_called()
        resume.assert_called_once_with(lease, stopping=False, recovery_instance=71,
                                       fixture_maintenance=False)
