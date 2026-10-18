"""Host-only history guards; native packages, GDM and processes are doubles."""

import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_native_update as history


@pytest.fixture
def private(tmp_path, monkeypatch):
    directory = tmp_path / 'private'
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(history, 'private', lambda: directory)
    return directory


def test_checkpoints_are_append_only_and_reject_phase_splicing(private, monkeypatch):
    binding = {'run': 'a' * 32, 'native_binding_sha256': 'b' * 64}
    history.save('old', binding, boot='old-boot')
    original = (private / 'native-update-old.json').read_bytes()
    with pytest.raises(FileExistsError):
        history.save('old', binding, boot='replacement')
    assert (private / 'native-update-old.json').read_bytes() == original
    monkeypatch.setattr(history, 'read_private', lambda path: json.loads(path.read_text()))
    assert history.checkpoint('old', binding)['boot'] == 'old-boot'
    with pytest.raises(history.guest.GuestError, match='checkpoint-attempt'):
        history.checkpoint('old', dict(binding, run='c' * 32))
    value = json.loads(original)
    value['phase'] = 'updated'
    monkeypatch.setattr(history, 'read_private', lambda path: value)
    with pytest.raises(history.guest.GuestError, match='checkpoint-attempt'):
        history.checkpoint('old', binding)


@pytest.mark.parametrize('fault', ['symlink', 'hardlink', 'writable', 'oversize', 'foreign'])
def test_private_checkpoint_refuses_unsafe_metadata(private, monkeypatch, fault):
    path = private / 'state.json'
    path.write_text('{}')
    path.chmod(0o600)
    if fault == 'symlink':
        link = private / 'link'
        link.symlink_to(path)
        with pytest.raises(OSError):
            history.read_private(link)
        return
    actual = history.os.fstat

    def metadata(descriptor):
        info = actual(descriptor)
        return SimpleNamespace(st_mode=info.st_mode | (0o020 if fault == 'writable' else 0),
            st_uid=1001 if fault == 'foreign' else 0, st_gid=0,
            st_nlink=2 if fault == 'hardlink' else 1,
            st_size=9 * 1024 * 1024 if fault == 'oversize' else info.st_size)

    monkeypatch.setattr(history.os, 'fstat', metadata)
    with pytest.raises(history.guest.GuestError, match='checkpoint-metadata'):
        history.read_private(path)


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('fault', [None, 'selection', 'baseline', 'manifest', 'format'])
def test_staged_input_binding_covers_every_attempt_input(tmp_path, monkeypatch, package_format, fault):
    monkeypatch.setattr(history.guest, 'PAYLOAD', tmp_path)
    marker = {key: hashlib.sha256(key.encode()).hexdigest() for key in (
        'package_sha256', 'preparation_sha256', 'baseline_sha256', 'selected_inputs_sha256')}
    marker.update(run='a' * 32, machine_id='guest', domain_uuid='uuid')
    (tmp_path / 'selected-inputs.json').write_text('{}')
    marker['selected_inputs_sha256'] = history.guest.sha(tmp_path / 'selected-inputs.json')
    directory = tmp_path / 'native-transaction'
    directory.mkdir()
    manifest = {'pair_id': 'finite-pair', 'package_format': package_format,
                'binding_sha256': 'c' * 64}
    (directory / 'native-inputs.json').write_text(json.dumps(manifest))
    binding = {'schema_version': 1, 'pair_id': 'finite-pair', 'package_format': package_format,
        'native_manifest_sha256': history.guest.sha(directory / 'native-inputs.json'),
        'baseline_provenance_sha256': marker['baseline_sha256'],
        'selected_inputs_sha256': marker['selected_inputs_sha256']}
    changed = {'selection': 'selected_inputs_sha256', 'baseline': 'baseline_provenance_sha256',
               'manifest': 'native_manifest_sha256', 'format': 'package_format'}
    if fault:
        binding[changed[fault]] = 'wrong'
    (tmp_path / 'native-transaction-binding.json').write_text(json.dumps(binding))
    monkeypatch.setattr(history.guest, 'guard', lambda: marker)
    monkeypatch.setattr(history.guest, 'package_path', lambda: tmp_path / ('package.' + package_format))
    monkeypatch.setattr(history.native, 'validate_manifest', lambda *args: ({}, {}, {}))
    if fault:
        with pytest.raises(history.guest.GuestError, match='staged-binding'):
            history.inputs()
    else:
        result, actual, path = history.inputs()
        assert result['run'] == marker['run'] and result['native_binding_sha256'] == 'c' * 64
        assert result['baseline_sha256'] == marker['baseline_sha256']
        assert actual == manifest and path == directory


def test_old_native_transaction_precedes_any_product_admission(private, monkeypatch):
    events = []
    monkeypatch.setattr(history, 'inputs', lambda: ({'run': 'owned'}, {'pair': 'finite'}, 'bundle'))
    monkeypatch.setattr(history.guest, 'before_install', lambda: events.append('product-free'))
    monkeypatch.setattr(history.guest, 'enable_diagnostics', lambda: None)
    monkeypatch.setattr(history, 'preflight', lambda *args: events.append('preflight') or {'read_only': True})
    monkeypatch.setattr(history, 'transaction', lambda *args: events.append('old-native'))
    monkeypatch.setattr(history, 'native_identity', lambda *args: {'sha256': 'old'})
    monkeypatch.setattr(history, 'BOOT', SimpleNamespace(read_text=lambda: 'initial-boot'))
    history.establish_old()
    assert events == ['product-free', 'preflight', 'old-native']
    assert json.loads((private / 'native-update-intent.json').read_text())['preflight']['read_only']
    assert json.loads((private / 'native-update-old.json').read_text())['native']['sha256'] == 'old'
    with pytest.raises(history.guest.GuestError, match='already-started'):
        history.establish_old()
    assert events.count('old-native') == 1


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_native_transaction_is_one_local_package_with_normal_triggers(private, monkeypatch, package_format):
    manifest = {'package_format': package_format, 'selection': {'package': 'selected'},
                'packages': {'new': {'path': 'new.' + package_format}}}
    installed = ({'selected:amd64': {'Package': 'selected'}, 'libc:amd64': {'Package': 'libc'}}
                 if package_format == 'deb' else [{'name': 'selected'}, {'name': 'libc'}])
    triggers = {'applicable': ['man-db'], 'completion_unit': 'man-db-cache-update.service'}
    before = {'native_state': {'installed': installed, 'triggers': triggers}}
    command = Mock(return_value=SimpleNamespace(returncode=0,
        stdout='Processing triggers for man-db (2.13) ...'))
    monkeypatch.setattr(history, 'GuestRunner', lambda: SimpleNamespace(run=command))
    monkeypatch.setattr(history, 'preflight', lambda *args: copy.deepcopy(before))
    monkeypatch.setattr(history, 'native_identity', lambda *args: {'sha256': 'new'})
    monkeypatch.setattr(history, 'cache_result', lambda *args: {'branch': 'completed'})
    monkeypatch.setattr(history.time, 'monotonic', lambda: 1.0)
    monkeypatch.setattr(history.native, 'rpm_trigger_idle', lambda *args: {'Result': 'success'})

    def run(arguments, **kwargs):
        if arguments[0] == 'systemctl':
            return 'ExecMainStartTimestampMonotonic=1000001\nExecMainExitTimestampMonotonic=1000002\nExecMainStatus=0'
        return json.dumps({'UNIT': 'man-db-cache-update.service', 'JOB_TYPE': 'start', 'JOB_RESULT': 'done'})
    monkeypatch.setattr(history.guest, 'run', run)
    history.transaction({}, manifest, Path('/owned-bundle'), 'new', before, lambda *_: None)
    argv = command.call_args.args[0]
    assert argv == (['dpkg', '--install', '/owned-bundle/new.deb'] if package_format == 'deb' else
                    ['rpm', '--upgrade', '--oldpackage', '--replacepkgs', '/owned-bundle/new.rpm'])
    assert command.call_args.kwargs == {'timeout': 180}
    assert (private / 'native-update-output/new.txt').is_file()


@pytest.mark.parametrize('fault', ['new-version', 'same-bytes', 'source-instead-of-private'])
def test_bwrap_inventory_requires_actual_substituted_native_record(monkeypatch, fault):
    record = dict(role='bwrap-native', source='/usr/bin/bwrap',
                  path='/usr/libexec/oh-no-parent-control-kiosk-bwrap', sha256='old')
    if fault == 'source-instead-of-private':
        record['path'] = '/usr/bin/bwrap'
    if fault in ('new-version', 'same-bytes'):
        record['role'] = 'bwrap'
    with pytest.raises(history.guest.GuestError, match='bwrap-substitution'):
        history.measured_record({'selection': {'executable': '/usr/bin/bwrap'}, 'package_format': 'deb'},
            {'inventory': lambda config: [record]}, {})


def test_partial_witness_setup_closes_first_owned_descriptor(private, tmp_path, monkeypatch):
    fd = os.open(os.devnull, os.O_RDONLY)
    monkeypatch.setattr(history.os, 'pidfd_open', lambda pid: fd)
    monkeypatch.setattr(history.confinement, 'PROC', tmp_path)
    boundary = {'pid': 4321}
    with pytest.raises(FileNotFoundError):
        with history.native_witness(SimpleNamespace(pw_uid=1001), boundary,
                                    {'package_format': 'deb'}, lambda *_: None):
            pytest.fail('setup failure must not enter the observation')
    with pytest.raises(OSError):
        os.fstat(fd)


def test_stale_admission_requires_own_exact_reason(private, monkeypatch):
    monkeypatch.setattr(history.guest, 'commands', SimpleNamespace(sequence=0, directory=None))
    def refused(*args, **kwargs):
        os.write(2, b'onpc.kiosk confinement outcome=failed reason=stale-manager-reboot-required\n')
        return 125, b'{"pam": 14}'
    monkeypatch.setattr(history.confinement, 'first_exec', refused)
    history.stale_admission(None, lambda *_: None)
    assert b'stale-manager-reboot-required' in (private / 'native-update-output/stale-admission.txt').read_bytes()


def test_generic_pam_refusal_cannot_prove_stale_generation(private, monkeypatch):
    monkeypatch.setattr(history.guest, 'commands', SimpleNamespace(sequence=0, directory=None))
    monkeypatch.setattr(history.confinement, 'first_exec', lambda *args, **kwargs: (125, b'{"pam": 14}'))
    with pytest.raises(history.guest.GuestError, match='stale-manager-reason'):
        history.stale_admission(None, lambda *_: None)


def test_fresh_phase_requires_retired_phase_and_changed_boot(monkeypatch):
    monkeypatch.setattr(history, 'inputs', lambda: ({'run': 'owned'}, {}, None))
    phases = []
    monkeypatch.setattr(history, 'checkpoint', lambda phase, binding:
                        phases.append(phase) or {'boot': 'same-boot'})
    monkeypatch.setattr(history, 'BOOT', SimpleNamespace(read_text=lambda: 'same-boot'))
    installed = Mock()
    monkeypatch.setattr(history.guest, 'installed', installed)
    with pytest.raises(history.guest.GuestError, match='recovery-reboot-required'):
        history.fresh_after_reboot(lambda *_: None)
    assert phases == ['retired', 'updated']
    installed.assert_not_called()


def test_proxy_worker_cannot_bypass_app_role(monkeypatch):
    monkeypatch.setattr(history.confinement, 'lifecycle_label', lambda backend: 'unconfined_t')
    execute = Mock()
    monkeypatch.setattr(history.os, 'execve', execute)
    with pytest.raises(history.guest.GuestError, match='proxy-app-entry'):
        history.proxy_exec(dict(uid=1001, gid=1001, namespace=88, generation='a' * 64 + '\n', ready_fd=12))
    execute.assert_not_called()


@pytest.mark.parametrize('status', [0, -1])
def test_fedora_entry_uses_private_app_entrypoint_before_native_proxy(tmp_path, monkeypatch, status):
    pending = Mock(return_value=status)
    monkeypatch.setattr(history.ctypes, 'CDLL', lambda *args, **kwargs:
                        SimpleNamespace(setexeccon=pending))
    execute = Mock()
    monkeypatch.setattr(history.os, 'execve', execute)
    caller = tmp_path / 'private-python-entrypoint'
    request = dict(uid=1001, gid=1001, namespace=88, generation='a' * 64 + '\n', ready_fd=12)
    if status:
        with pytest.raises(history.guest.GuestError, match='proxy-role-entry'):
            history.enter_proxy(caller, request)
        execute.assert_not_called()
    else:
        history.enter_proxy(caller, request)
        argv = execute.call_args.args
        assert argv[0] == str(caller)
        assert argv[1][:4] == [str(caller), '-B', str(Path(history.__file__).resolve()), 'proxy-exec']
        assert json.loads(argv[1][4]) == request
        assert argv[2] == {'PATH': '/usr/bin:/bin', 'LANG': 'C'}
    pending.assert_called_once_with(b'system_u:system_r:onpc_kiosk_app_t:s0')


def test_socket_replacement_refusal_still_closes_all_witness_descriptors(tmp_path):
    replacement = tmp_path / 'foreign-socket'
    replacement.write_bytes(b'preserve foreign input')
    descriptors = os.pipe2(os.O_CLOEXEC)
    with pytest.raises(history.guest.GuestError, match='proxy-socket-replaced'):
        history.cleanup_witness(None, None, True, replacement, (0, 0),
                                os.getuid(), set(descriptors), None)
    assert replacement.read_bytes() == b'preserve foreign input'
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_owned_child_cleanup_failure_still_closes_descriptors(tmp_path, monkeypatch):
    descriptors = os.pipe2(os.O_CLOEXEC)
    monkeypatch.setattr(history.signal, 'pidfd_send_signal', lambda *args: None)
    monkeypatch.setattr(history.os, 'waitpid', Mock(side_effect=ChildProcessError('owned wait failed')))
    with pytest.raises(ChildProcessError, match='owned wait failed'):
        history.cleanup_witness(4321, descriptors[0], False, tmp_path / 'absent', None,
                                os.getuid(), {descriptors[1]}, None)
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


@pytest.mark.parametrize('fault', [None, 'hash', 'inode', 'credentials', 'generation', 'label'])
def test_retained_mapping_requires_real_executable_and_enforcing_identity(tmp_path, monkeypatch, fault):
    proc = tmp_path / 'proc'
    process = proc / '4321'
    process.mkdir(parents=True)
    executable = tmp_path / 'old-native'
    executable.write_bytes(b'old native executable A')
    (process / 'exe').symlink_to(executable)
    marker = process / 'root' / history.GENERATION
    marker.parent.mkdir(parents=True)
    marker.write_text(('b' if fault == 'generation' else 'a') * 64 + '\n')
    attribute = process / 'attr/apparmor/current'
    attribute.parent.mkdir(parents=True)
    attribute.write_text('unconfined' if fault == 'label' else 'onpc-kiosk-bwrap (enforce)')
    (process / 'ns').mkdir()
    (process / 'ns/mnt').symlink_to('mnt:[456]')
    (proc / '1/ns').mkdir(parents=True)
    (proc / '1/ns/mnt').symlink_to('mnt:[1]')
    info = executable.stat()
    (process / 'maps').write_text('1000-2000 r-xp 00000000 '
        f'{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x} '
        f'{info.st_ino + (1 if fault == "inode" else 0)} /private/native\n')
    monkeypatch.setattr(history.confinement, 'PROC', proc)
    monkeypatch.setattr(history.confinement, 'process_identity', lambda path:
        ('123', 10, ('1002' if fault == 'credentials' else '1001',) * 4))
    expected = {'sha256': 'wrong' if fault == 'hash' else history.guest.sha(executable)}
    if fault:
        with pytest.raises(history.guest.GuestError, match='native-update:'):
            history.mapping(4321, SimpleNamespace(pw_uid=1001), 'apparmor',
                            'a' * 64 + '\n', expected, 'bwrap')
    else:
        result = history.mapping(4321, SimpleNamespace(pw_uid=1001), 'apparmor',
                                 'a' * 64 + '\n', expected, 'bwrap')
        assert result['inode'] == info.st_ino and result['sha256'] == expected['sha256']
        assert result['mappings'] and result['identity'][0] == '123'


@pytest.mark.parametrize('failure', ['native-status', 'missing-trigger', 'extra-package'])
def test_native_transaction_failure_preserves_output_and_refuses_success(private, monkeypatch, failure):
    manifest = {'package_format': 'deb', 'selection': {'package': 'selected'},
                'packages': {'new': {'path': 'new.deb'}}}
    before = {'native_state': {'installed': {'selected': {'Package': 'selected'}},
                              'triggers': {'applicable': ['man-db']}}}
    after = copy.deepcopy(before)
    if failure == 'extra-package':
        after['native_state']['installed']['unexpected'] = {'Package': 'unexpected'}
    monkeypatch.setattr(history, 'GuestRunner', lambda: SimpleNamespace(run=lambda *args, **kwargs:
        SimpleNamespace(returncode=1 if failure == 'native-status' else 0,
            stdout='No trigger' if failure == 'missing-trigger' else 'Processing triggers for man-db (2) ...')))
    monkeypatch.setattr(history, 'native_identity', lambda *args: {})
    monkeypatch.setattr(history, 'preflight', lambda *args: after)
    monkeypatch.setattr(history, 'cache_result', lambda *args: pytest.fail('cannot accept failed transaction'))
    with pytest.raises(history.guest.GuestError, match={
            'native-status': 'native-transaction-failed', 'missing-trigger': 'trigger-not-observed',
            'extra-package': 'unrelated-native-changes'}[failure]):
        history.transaction({}, manifest, Path('/owned'), 'new', before, lambda *_: None)
    assert (private / 'native-update-output/new.txt').exists()


@pytest.mark.parametrize('failure', [None, 'mapping', 'denial'])
def test_complete_retained_phase_requires_every_boundary_before_checkpoint(private, tmp_path, monkeypatch, failure):
    import runpy
    events = []
    binding = {'run': 'owned'}
    manifest = {'package_format': 'deb', 'selection': {'executable': '/usr/bin/bwrap'},
                'packages': {'old': {'executable': {'sha256': 'old'}}}}
    boundary = {'pid': 4321, 'generation': 'a' * 64 + '\n'}
    account = SimpleNamespace(pw_uid=1001)
    config = tmp_path / 'config.json'
    config.write_text('{"backend":"apparmor"}')
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    monkeypatch.setattr(history, 'CONFIG', config)
    monkeypatch.setattr(history, 'RUNTIME', runtime)
    monkeypatch.setattr(history, 'inputs', lambda: (binding, manifest, 'bundle'))
    monkeypatch.setattr(history, 'checkpoint', lambda *args: {'boot': 'initial'})
    monkeypatch.setattr(history, 'BOOT', SimpleNamespace(read_text=lambda: 'retained-boot'))
    monkeypatch.setattr(history.guest, 'installed', lambda: events.append('installed'))
    monkeypatch.setattr(history.guest, 'enable_diagnostics', lambda: None)
    monkeypatch.setattr(history, 'native_identity', lambda *args: events.append('old-native-identity'))
    monkeypatch.setattr(history.pwd, 'getpwnam', lambda name: account)
    monkeypatch.setattr(runpy, 'run_path', lambda path: {'enforcing': lambda config: events.append('enforcing')})
    monkeypatch.setattr(history.confinement, 'manager_boundary', lambda *args: boundary)
    monkeypatch.setattr(history, 'measured_record', lambda *args:
                        {'sha256': 'old', 'path': '/usr/libexec/oh-no-parent-control-kiosk-bwrap'})
    monkeypatch.setattr(history, 'policy_state', lambda **kwargs: {'saved-policy': 'unchanged'})
    monkeypatch.setattr(history.guest, 'pam_service_state', lambda: {'vendor': 'unchanged'})
    monkeypatch.setattr(history, 'preflight', lambda *args: {})
    monkeypatch.setattr(history, 'save', lambda phase, *args, **kwargs: events.append('save-' + phase))
    upgraded = False

    @contextmanager
    def witness(*args):
        events.append('retain-native-A')
        yield lambda: {'mapping': 'B' if upgraded and failure == 'mapping' else 'A'}
        events.append('retire-native-witness')
    monkeypatch.setattr(history, 'native_witness', witness)

    def transact(*args):
        nonlocal upgraded
        events.append('native-transaction')
        upgraded = True
    monkeypatch.setattr(history, 'transaction', transact)
    monkeypatch.setattr(history.guest, 'sha', lambda path: 'old' if '/root/' in str(path) else 'new')

    def control(account, backend, record, stage):
        events.append('controls-' + stage)
        if failure == 'denial' and stage == 'updated':
            raise history.guest.GuestError('native-update:missing-kernel-denial')
    monkeypatch.setattr(history, 'controls', control)
    monkeypatch.setattr(history, 'stale_admission', lambda *args: events.append('stale-refused'))
    monkeypatch.setattr(history.confinement, 'verify_loader_admission_refusal',
                        lambda *args: events.append('held-loader-refused'))

    def run(arguments, **kwargs):
        if '--property=Type' in arguments:
            return 'notify-reload'
        if '--property=ReloadSignal' in arguments:
            return '59'
        assert arguments[:2] == ['systemctl', 'reload']
        events.append('manager-reexec')
        return ''
    monkeypatch.setattr(history.guest, 'run', run)
    if failure:
        with pytest.raises(history.guest.GuestError):
            history.retain_upgrade(lambda *_: None)
        assert 'save-updated' not in events
    else:
        history.retain_upgrade(lambda *_: None)
        expected = ['installed', 'old-native-identity', 'save-retained-intent', 'controls-before',
            'retain-native-A', 'native-transaction', 'controls-updated', 'stale-refused',
            'held-loader-refused', 'manager-reexec', 'controls-reexec',
            'retire-native-witness', 'save-updated']
        assert [event for event in events if event != 'enforcing'] == expected


@pytest.mark.parametrize('failure', [None, 'policy', 'same-generation', 'old-runtime'])
def test_rebooted_public_station_requires_B_policy_native_enforcement_and_broker(private, tmp_path, monkeypatch, failure):
    import runpy
    import system_enforcement
    events = []
    manifest = {'packages': {'new': {'executable': {'sha256': 'new'}}}}
    policy = {'child': 1002}
    updated = {'policy': policy, 'pam': {'saved': True}, 'boundary': {'generation': 'a' * 64 + '\n'}}
    monkeypatch.setattr(history, 'inputs', lambda: ({'run': 'owned'}, manifest, None))
    monkeypatch.setattr(history, 'checkpoint', lambda phase, binding:
                        {'boot': 'old-boot'} if phase == 'retired' else updated)
    monkeypatch.setattr(history, 'BOOT', SimpleNamespace(read_text=lambda: 'new-boot'))
    monkeypatch.setattr(history.guest, 'installed', lambda: events.append('installed'))
    monkeypatch.setattr(history, 'native_identity', lambda *args: events.append('new-native-identity'))
    monkeypatch.setattr(history, 'policy_state', lambda: {'changed': True} if failure == 'policy' else policy)
    monkeypatch.setattr(history.guest, 'pam_service_state', lambda: {'saved': True})
    monkeypatch.setattr(history.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1001))
    config = tmp_path / 'config.json'
    config.write_text('{"backend":"apparmor"}')
    monkeypatch.setattr(history, 'CONFIG', config)
    monkeypatch.setattr(runpy, 'run_path', lambda path: {})
    monkeypatch.setattr(history, 'measured_record', lambda *args: {'sha256': 'new', 'path': '/usr/bin/selected'})
    monkeypatch.setattr(history.confinement, 'manager_boundary', lambda *args:
        {'pid': 4322, 'generation': ('a' if failure == 'same-generation' else 'b') * 64 + '\n'})
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    if failure == 'old-runtime':
        (runtime / ('a' * 64)).mkdir()
    monkeypatch.setattr(history, 'RUNTIME', runtime)
    monkeypatch.setattr(history.guest, 'sha', lambda path: 'new')
    monkeypatch.setattr(history, 'controls', lambda *args: events.append('fresh-enforcement'))
    monkeypatch.setattr(system_enforcement, 'call', lambda *args: events.append('public-kiosk-broker') or [[[1002, '', '']]])
    monkeypatch.setattr(history, 'save', lambda phase, *args, **kwargs: events.append('save-' + phase))
    if failure:
        with pytest.raises(history.guest.GuestError):
            history.fresh_after_reboot(lambda *_: None)
        assert 'save-complete' not in events
    else:
        history.fresh_after_reboot(lambda *_: None)
        assert events == ['installed', 'new-native-identity', 'fresh-enforcement', 'public-kiosk-broker', 'save-complete']
