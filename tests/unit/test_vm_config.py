"""Configuration selection and provenance isolation without accessing real VMs."""
from tests.support.vm_registry import vm_name

import json
import fcntl
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

import prepare_baseline as host
import prepare_vm as guest
import vm_config
import system_runner as runner
from tests.support.paths import ROOT
from tests.support.vm_baseline import UUID, xml, rig
from tests.support.vm_runner import lease_rig


def write_config(tmp_path, **changes):
    path = tmp_path / 'test-vm.json'
    document = {'name': 'custom-test-vm', 'disk_anchor': '/images/base.qcow2'}
    path.write_text(json.dumps({'vms': [{**document, **changes}]}))
    return path


def test_shared_config_selects_domain_hostname_disk_and_separate_state(tmp_path):
    configured = vm_config.load('custom-test-vm', write_config(tmp_path))
    assert configured.name == 'custom-test-vm'
    assert configured.disk_anchor == Path('/images/base.qcow2')
    assert configured.baseline_directory == vm_config.STATE_ROOT / 'custom-test-vm'
    assert host.DOMAIN == vm_config.selected().name
    assert guest.HOSTNAME == vm_config.selected().hostname
    assert host.ANCHOR == vm_config.selected().disk_anchor
    assert host.BASELINES == vm_config.selected().baseline_directory


@pytest.mark.parametrize('changes', [
    {'name': ''}, {'name': '../another'}, {'name': '-flag'}, {'name': 'vm\nname'},
    {'name': 'vm..name'}, {'name': 'x' * 64}, {'name': None},
    {'name': []}, {'disk_anchor': 'relative.qcow2'}, {'disk_anchor': '/images/../disk'},
    {'disk_anchor': '/images//disk'}, {'disk_anchor': '/images/disk\n'},
    {'disk_anchor': None}, {'unexpected': True},
])
def test_invalid_config_is_refused_before_resource_access(tmp_path, changes):
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.registry(write_config(tmp_path, **changes))


@pytest.mark.parametrize('contents', ['{', '[]', '{}',
    '{"name":"first","name":"second","disk_anchor":"/disk"}'])
def test_malformed_or_ambiguous_configuration_is_refused(tmp_path, contents):
    path = tmp_path / 'test-vm.json'
    path.write_text(contents)
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.registry(path)


def test_missing_configuration_has_no_hardcoded_vm_fallback(tmp_path):
    with pytest.raises(ValueError, match='vm-config:unreadable'):
        vm_config.load('custom-test-vm', tmp_path / 'absent')


def test_display_name_preserves_case_and_hostname_is_lowercase(tmp_path):
    configured = vm_config.load('custom-Ubuntu26.04', write_config(tmp_path, name='custom-Ubuntu26.04'))
    assert configured.name == 'custom-Ubuntu26.04'
    assert configured.hostname == 'custom-ubuntu26.04'
    assert configured.baseline_directory.name == configured.name


def test_configured_vm_names_have_no_literal_in_code_or_documentation():
    # The configured display name belongs in config, not its consumers.
    names = list(vm_config.registry())
    for directory in ('tools', 'tests', 'docs'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and path.suffix in ('', '.py', '.md', '.MD', '.json', '.rules', '.sh'):
                contents = path.read_text()
                assert not any(name in contents for name in names), str(path.relative_to(ROOT))
    for relative in ('setup.sh', 'Makefile'):
        assert not any(name in (ROOT / relative).read_text() for name in names)


@pytest.fixture
def selector_config(tmp_path, monkeypatch):
    path = tmp_path / 'config/test-vm.json'
    path.parent.mkdir()
    document = {'concurrency': 2, 'vms': [
        {'id': '17', 'name': 'Alpha-guest', 'disk_anchor': '/alpha', 'enabled': 'true'},
        {'id': 83, 'name': 'Beta-guest', 'disk_anchor': '/beta', 'enabled': 'true'}]}
    path.write_text(json.dumps(document))
    monkeypatch.setattr(vm_config, 'CONFIG', path)
    return path, document


@pytest.mark.parametrize('equal_form', [False, True])
def test_ids_are_fresh_lookups_after_swapping_in_the_same_process(selector_config, equal_form):
    path, document = selector_config
    for swapped in (False, True):
        if swapped:
            first, second = document['vms']
            first['id'], second['id'] = second['id'], first['id']
            path.write_text(json.dumps(document))
        for entry in document['vms']:
            identifier = str(entry['id'])
            by_name = vm_config.load(entry['name'])
            assert vm_config.load(identifier) == by_name
            assert vm_config.execution(identifier) == vm_config.execution(entry['name'])
            option = ['--vm=' + identifier] if equal_form else ['--vm', identifier]
            args, configured = vm_config.extract(['status', *option])
            assert args == ['status'] and configured == by_name
            assert os.environ[vm_config.VARIABLE] == entry['name']
            assert vm_config.arguments() == ['--vm', entry['name']]
            assert host.DOMAIN == entry['name'] and guest.HOSTNAME == entry['name'].lower()


@pytest.mark.parametrize('identifier', [None, '', '0', 0, -1, True, '01', '1.5', ' 17', 'guest', [], {}])
def test_invalid_ids_fail_closed(selector_config, identifier):
    path, document = selector_config
    document['vms'][0]['id'] = identifier
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='vm-config:id'):
        vm_config.registry()


@pytest.mark.parametrize('collision', ['duplicate', 'name'])
def test_ids_cannot_ambiguously_select_another_guest(selector_config, collision):
    path, document = selector_config
    if collision == 'duplicate':
        document['vms'][1]['id'] = int(document['vms'][0]['id'])
    else:
        document['vms'][1]['name'] = document['vms'][0]['id']
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='vm-config:(duplicate-id|ambiguous-id-or-name)'):
        vm_config.load('17')


def test_deleted_id_never_uses_an_earlier_lookup(selector_config):
    path, document = selector_config
    assert vm_config.load('17').name == 'Alpha-guest'
    document['vms'][0]['id'] = '96'
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='unknown-vm'):
        vm_config.load('17')
    assert vm_config.load('96').name == 'Alpha-guest'


def test_all_and_make_vm_selectors_rebind_from_json(selector_config):
    import runpy
    import test_commands
    from vm_selection import make_command, execution_binding
    path, document = selector_config
    make_e2e = runpy.run_path(str(ROOT / 'tests/e2e/runner.py'))['make_arguments']
    for entry in document['vms']:
        for selector in (str(entry['id']), entry['name']):
            args, selected = test_commands.vm_request(['all', '--vm', selector])
            assert args == ['all'] and selected.name == entry['name']
            assert execution_binding() == entry['name']
            for target in ('all', 'all-verify', 'system', 'appsnapshot'):
                command = make_command(ROOT, target, {'ONPC_MAKE_VM': selector})
                assert command[-2:] == ['--vm', entry['name']]
            assert make_e2e({'ONPC_E2E_VM': selector}) == ['--vm', entry['name']]
    document['vms'][0]['id'], document['vms'][1]['id'] = (
        document['vms'][1]['id'], document['vms'][0]['id'])
    path.write_text(json.dumps(document))
    assert make_command(ROOT, 'all', {'ONPC_MAKE_VM': '17'})[-1] == 'Beta-guest'
    assert make_e2e({'ONPC_E2E_VM': '17'}) == ['--vm', 'Beta-guest']
    test_commands.vm_request(['all', '--vm', '17'])
    assert execution_binding() == 'Beta-guest'


def test_agent_launchers_resolve_current_ids_before_session_creation(selector_config, monkeypatch):
    import fix_tests
    import write_e2e
    import vm_selection
    path, document = selector_config
    monkeypatch.setattr(fix_tests, 'select', Mock(return_value=(None, False)))
    monkeypatch.setattr(write_e2e.launcher, 'select', Mock(return_value=(None, False)))
    for swapped in (False, True):
        if swapped:
            first, second = document['vms']
            first['id'], second['id'] = second['id'], first['id']
            path.write_text(json.dumps(document))
        for entry in document['vms']:
            for selector in (str(entry['id']), entry['name']):
                assert fix_tests.main(['system', '--vm', selector]) == 0
                assert vm_selection.execution_binding() == entry['name']
                assert write_e2e.select(ROOT, ['--vm', selector]) == (None, False)
                assert vm_selection.execution_binding() == entry['name']


def test_disabled_vm_id_has_the_same_execution_guard_as_its_name(selector_config):
    path, document = selector_config
    document['vms'][1]['enabled'] = 'false'
    path.write_text(json.dumps(document))
    assert vm_config.load('83') == vm_config.load('Beta-guest')
    for selector in ('83', 'Beta-guest'):
        with pytest.raises(ValueError, match='no enabled'):
            vm_config.execution(selector)


def test_installed_dispatcher_keeps_uuid_pins_by_name_when_ids_swap(selector_config):
    import runpy
    path, document = selector_config
    root = path.parent.parent
    controller = root / 'tests/integration/vm_control.py'
    controller.parent.mkdir(parents=True)
    controller.write_text('# private command target; never executed\n')
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    pins = {'Alpha-guest': UUID, 'Beta-guest': '33d86c8c-3b87-4c7b-9520-2df0b7e21e16'}
    dispatch.__globals__['VM_UUIDS'] = pins
    for swapped in (False, True):
        if swapped:
            first, second = document['vms']
            first['id'], second['id'] = second['id'], first['id']
            path.write_text(json.dumps(document))
        for entry in document['vms']:
            by_id = dispatch(root, ['vm', 'status', '--vm', str(entry['id'])])
            assert by_id == dispatch(root, ['vm', 'status', '--vm', entry['name']])
            assert by_id[3:7] == ['--vm', entry['name'], '--expected-uuid', pins[entry['name']]]


def test_configuration_change_invalidates_guest_preparation_digest(tmp_path):
    for relative in guest.SCRIPT_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / relative).read_bytes())
    before = guest.preparation_digest(tmp_path)
    (tmp_path / 'config/test-vm.json').write_text(
        '{"name":"different-vm","disk_anchor":"/images/base.qcow2"}')
    assert guest.preparation_digest(tmp_path) != before


def test_id_changes_do_not_invalidate_guest_preparation_or_baseline_proof(tmp_path):
    for relative in guest.SCRIPT_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / relative).read_bytes())
    path = tmp_path / 'config/test-vm.json'
    document = json.loads(path.read_text())
    before = guest.preparation_digest(tmp_path)
    first, second = document['vms'][:2]
    first['id'], second['id'] = second['id'], first['id']
    path.write_text(json.dumps(document, indent=4))
    assert guest.preparation_digest(tmp_path) == before
    first['id'] = '97'
    path.write_text(json.dumps(document))
    assert guest.preparation_digest(tmp_path) == before
    first['name'] = 'renamed-guest'
    path.write_text(json.dumps(document))
    assert guest.preparation_digest(tmp_path) != before


def test_libvirt_selects_configured_name_and_still_rejects_replacement(monkeypatch, tmp_path):
    configured = vm_config.load('custom-test-vm', write_config(tmp_path))
    monkeypatch.setattr(host, 'DOMAIN', configured.name)
    domain = Mock()
    domain.UUIDString.return_value = UUID
    connection = Mock()
    connection.getURI.return_value = vm_config.URI
    connection.lookupByName.return_value = domain
    api = Mock()
    api.open.return_value = connection
    source = host.LibvirtSource(api)
    connection.lookupByName.assert_called_once_with('custom-test-vm')
    host.domain_layout(xml('/images/base.qcow2'), UUID)
    with pytest.raises(host.CaptureError, match='domain-identity'):
        host.domain_layout(xml('/images/base.qcow2').replace('custom-test-vm', 'old-vm'), UUID)
    domain.UUIDString.return_value = '0' * 36
    with pytest.raises(host.CaptureError, match='domain-identity'):
        source.snapshot()
    source.close()


def test_state_root_creation_is_repeatable_and_preserves_legacy_record(tmp_path):
    directory = tmp_path / 'state'
    host.prepare_state_root(directory)
    legacy = directory / 'phase.json'
    legacy.write_bytes(b'original accepted baseline')
    identity = directory.stat().st_ino
    host.prepare_state_root(directory)
    assert directory.stat().st_ino == identity
    assert legacy.read_bytes() == b'original accepted baseline'
    assert directory.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('fault', ['permissions', 'symlink', 'owner'])
def test_unsafe_state_root_is_refused_without_repair(tmp_path, monkeypatch, fault):
    directory = tmp_path / 'state'
    directory.mkdir(mode=0o700)
    if fault == 'permissions':
        directory.chmod(0o755)
    elif fault == 'symlink':
        link = tmp_path / 'link'
        link.symlink_to(directory)
        directory = link
    else:
        monkeypatch.setattr(host.os, 'geteuid', lambda: os.getuid() + 1)
    with pytest.raises(host.CaptureError, match='guard:'):
        host.prepare_state_root(directory)


def test_named_vms_have_separate_leases_and_same_vm_refuses_concurrent_capture(rig, monkeypatch):
    state_root = rig.directory.parent
    monkeypatch.setattr(vm_config, 'STATE_ROOT', state_root)
    capture = rig.capture()
    capture.run()
    other_directory = state_root / 'another-vm'
    other_directory.mkdir(mode=0o700)
    other = host.Capture(rig.source, rig.commands, rig.inspect,
                         anchor=rig.anchor, directory=other_directory)
    assert capture.lock_path != other.lock_path
    assert capture.lock_path == capture.directory / '.lock'
    with capture.lock_path.open('rb') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(host.CaptureError, match='busy-controller'):
            capture.run()
        with other.lock_path.open('wb') as other_lock:
            fcntl.flock(other_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert len(rig.source.creations) == 1
    assert not (other_directory / 'phase.json').exists()


def test_shared_lock_is_used_by_runner_and_backing_ownership_checks(lease_rig, monkeypatch):
    lease, current = lease_rig
    local_lock = lease.capture.lock_path
    monkeypatch.setattr(vm_config, 'STATE_ROOT', lease.directory.parent)
    local_lock.rename(lease.capture.lock_path)
    with lease.capture.lock_path.open('rb') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(runner.Error, match='busy-controller'):
            lease.__enter__()
    with lease:
        lease.prepare()
        lease.start()
    assert lease.state['phase'] == 'complete'
    assert current['id'] == -1 and lease.source.off


def test_registry_contains_both_requested_vms():
    configured = vm_config.registry()
    assert configured[vm_name(1)].disk_anchor == Path(
        json.loads((ROOT / 'config/test-vm.json').read_text())['vms'][1]['disk_anchor'])
    assert vm_name() in configured


@pytest.mark.parametrize('name', [None, '', 'unknown-vm', vm_name(1).lower()])
def test_selection_requires_exact_configured_name(name):
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.load(name)


@pytest.mark.parametrize('entries', [[], [None], [
    {'name': 'first', 'disk_anchor': '/first'},
    {'name': 'first', 'disk_anchor': '/second'}], [
    {'name': 'first', 'disk_anchor': '/disk'},
    {'name': 'second', 'disk_anchor': '/disk'}]])
def test_registry_refuses_ambiguous_entries(tmp_path, entries):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'vms': entries}))
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.registry(path)


@pytest.mark.parametrize('argv', [[], ['--vm'], ['--vm=unknown-vm'],
    ['--vm', vm_name(), '--vm', vm_name(1)]])
def test_cli_selection_has_no_environment_or_default_fallback(argv):
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.extract(argv)


def test_guest_arguments_never_reselect_vm_or_trigger_host_help():
    guest = ['printf', '--vm', 'unknown-vm', '--help', '--list', '--vm=other']
    remaining, configured = vm_config.extract(['--vm', vm_name(), 'exec', '--', *guest])
    assert configured.name == vm_name()
    assert remaining == ['exec', '--', *guest]
    with pytest.raises(ValueError, match='--vm'):
        vm_config.extract(['exec', '--', *guest])


@pytest.mark.parametrize('args', [[], ['id'], ['--'], ['--', ''], ['--', '-o'],
    ['--timeout', '0', '--', 'id'], ['--timeout', '86401', '--', 'id'],
    ['--timeout', 'x', '--', 'id'], ['--host', 'other', '--', 'id'], ['--', 'id', '\0']])
def test_guest_command_controls_are_bounded_and_unambiguous(args):
    with pytest.raises(ValueError, match='vm-probe:'):
        vm_config.guest_command_arguments(args)


def test_guest_command_has_no_guest_program_allowlist_or_shell_interpolation():
    command = ['sh', '-c', 'journalctl; printf "%s" "$(id -u)"', '--vm', '--timeout', '--help']
    assert vm_config.guest_command_arguments(['--timeout', '600', '--', *command]) == (600, command, False)
    assert vm_config.guest_command_arguments(['--', 'id']) == (120, ['id'], False)
    assert vm_config.guest_command_arguments(['--stdin', '--', 'cat']) == (120, ['cat'], True)


def test_selection_updates_imported_controller_and_guest(monkeypatch):
    configured = vm_config.select(vm_name(1))
    assert host.DOMAIN == configured.name
    assert host.ANCHOR == configured.disk_anchor
    assert host.BASELINES == configured.baseline_directory
    assert guest.HOSTNAME == configured.hostname
    assert host.BASELINES != vm_config.load(vm_name()).baseline_directory


@pytest.mark.parametrize('command', [
    ['tools/test-vm', 'status'], ['tools/prepare-baseline', '--mode', 'auto'],
    ['tools/prepare-appsnapshot'], ['tools/cleanup-e2e'],
    ['tools/run-tests', 'system'], ['tools/run-tests', 'e2e'],
    ['tools/run-tests', 'integration', 'check_test_recovery'],
    ['tools/run-tests', 'all'], ['tools/write-e2e', '--tasks', '1'],
    ['tools/fix-tests', 'system'],
])
@pytest.mark.parametrize('options', [['--vm', 'unknown-vm']])
def test_public_vm_commands_refuse_before_privileges_resources_or_sessions(command, options):
    # Each short-lived process is owned by subprocess.run. Refusals create no
    # VM, display, socket, fixture, cache or shared output; compatible unit work.
    from tools.test_storage import scratch_descriptors
    result = subprocess.run([str(ROOT / command[0]), *command[1:], *options],
        cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15,
        pass_fds=scratch_descriptors())
    assert result.returncode != 0
    assert '--vm' in result.stderr or 'vm-config:' in result.stderr
    assert 'noninteractive authorization' not in result.stderr
    assert 'Started run-tests session' not in result.stderr
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize('concurrency', [0, -1, True, '2', 1.5, None])
def test_execution_refuses_invalid_concurrency(tmp_path, concurrency):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'concurrency': concurrency, 'vms': [
        {'name': 'first', 'disk_anchor': '/first', 'enabled': 'true'}]}))
    with pytest.raises(ValueError, match='concurrency'):
        vm_config.execution(path=path)


def test_execution_selects_only_literal_true_in_registry_order(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'concurrency': 2, 'vms': [
        {'name': 'first', 'disk_anchor': '/first', 'enabled': 'true'},
        {'name': 'disabled', 'disk_anchor': '/disabled', 'enabled': 'false'},
        {'name': 'missing', 'disk_anchor': '/missing'},
        {'name': 'last', 'disk_anchor': '/last', 'enabled': 'true'}]}))
    concurrency, vms = vm_config.execution(path=path)
    assert concurrency == 2 and [vm.name for vm in vms] == ['first', 'last']
    assert vm_config.execution('last', path)[0] == 1
    with pytest.raises(ValueError, match='no enabled'):
        vm_config.execution('disabled', path)
    with pytest.raises(ValueError, match='no enabled'):
        vm_config.execution('missing', path)


@pytest.mark.parametrize('concurrency', [1, 2, 3])
def test_vm_queue_refills_to_limit_and_executes_every_vm_after_failure(concurrency):
    # Only in-process threads and finite private state; no guest or shared cache.
    import threading
    import time
    from vm_test_queue import dispatch
    vms = [vm_config.VMConfig(f'guest-{index}', Path(f'/disk-{index}'), True) for index in range(7)]
    gate = threading.Lock()
    running, peak, attempts = 0, 0, []
    def execute(vm):
        nonlocal running, peak
        with gate:
            running += 1
            peak = max(peak, running)
            attempts.append(vm.name)
        time.sleep(.02)
        with gate:
            running -= 1
        return 1 if vm.name == 'guest-0' else 0
    results = dispatch(vms, concurrency, execute, threading.Event())
    assert peak == concurrency
    assert len(attempts) == len(set(attempts)) == len(vms)
    assert results == {vm.name: (1 if vm.name == 'guest-0' else 0) for vm in vms}


def test_isolated_vm_queue_worker_imports_then_refuses_nonprivate_entry(tmp_path):
    from tools.test_storage import scratch_descriptors
    # Owned short-lived process, private cwd, no VM or shared resource access.
    result = subprocess.run(
        ['/usr/bin/python3', '-IBu', str(ROOT / 'tools/vm_test_queue.py'),
         '--invalid', 'unused-vm'],
        cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=15, pass_fds=scratch_descriptors())
    assert result.returncode != 0
    assert 'private VM queue entry only' in result.stderr
    assert 'ModuleNotFoundError' not in result.stderr


def test_cancelled_vm_queue_never_starts_another_guest():
    import threading
    from vm_test_queue import dispatch
    stopped = threading.Event()
    vms = [vm_config.VMConfig(f'guest-{index}', Path(f'/disk-{index}'), True) for index in range(5)]
    attempts = []
    def execute(vm):
        attempts.append(vm.name)
        stopped.set()
        return 130
    assert set(dispatch(vms, 1, execute, stopped).values()) == {130}
    assert attempts == ['guest-0']


def test_batch_test_selection_and_explicit_diagnosis_obey_enabled_config(monkeypatch):
    import test_commands
    import vm_selection
    args, configured = test_commands.vm_request(['system'])
    assert args == ['system'] and configured is None
    assert vm_selection.execution_arguments() == []
    assert vm_selection.execution_binding()['vms'] == [vm_name()]
    with pytest.raises(ValueError, match='no enabled'):
        test_commands.vm_request(['system', '--vm', vm_name(1)])
    test_commands.vm_request(['system', '--vm', vm_name()])
    assert vm_selection.execution_arguments() == ['--vm', vm_name()]


def test_mixed_host_and_vm_categories_use_queue_without_reinterpreting_host_options():
    import test_commands
    import vm_selection
    assert test_commands.host_only_request(['unit', '-k', 'e2e'])
    assert not test_commands.host_only_request(['unit', 'system'])
    test_commands.vm_request(['unit', 'system'])
    assert vm_selection.execution_arguments() == []


def test_queue_cancellation_binding_survives_disabled_configuration(tmp_path):
    import vm_selection
    binding = {'concurrency': 2, 'vms': ['first', 'second']}
    vm_selection.save_binding(tmp_path, binding)
    vm_selection.check_binding(tmp_path, None, stopping=True)
    with pytest.raises(ValueError, match='original'):
        vm_selection.check_binding(tmp_path, None)


def test_legacy_controller_lease_excludes_all_named_leases(rig, monkeypatch):
    root = rig.directory.parent
    monkeypatch.setattr(vm_config, 'STATE_ROOT', root)
    legacy = root / '.lock'
    legacy.touch(mode=0o600)
    with legacy.open('rb') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            host.compatibility_lock(rig.directory)
    descriptors = [host.compatibility_lock(root / name) for name in ('first', 'second')]
    try:
        with legacy.open('rb') as lock:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def test_queue_controller_recovers_serially_runs_host_once_and_drains_guests(tmp_path, monkeypatch):
    from contextlib import contextmanager
    import threading
    import time
    import test_commands
    import vm_test_queue as queue
    import vm_selection
    vms = [vm_config.VMConfig(f'guest-{index}', Path(f'/disk-{index}'), True) for index in range(5)]
    monkeypatch.setenv(vm_selection.BATCH, json.dumps({'vms': [vm.name for vm in vms], 'concurrency': 2}))
    monkeypatch.setattr(vm_config, 'registry', lambda: {vm.name: vm for vm in vms})
    monkeypatch.setattr(queue.test_activity, 'retention_path', lambda root: tmp_path / 'journal')
    monkeypatch.setattr(queue.test_launcher, 'environment', lambda root: dict(os.environ))
    original_allocate = queue.test_retention.allocate
    monkeypatch.setattr(queue.test_retention, 'allocate',
                        lambda factory, **kwargs: original_allocate(factory, dir=tmp_path, **kwargs))
    hosts = []
    monkeypatch.setattr(test_commands, '_main', lambda argv, **kwargs: hosts.append(argv) or 0)
    monkeypatch.setattr(test_commands, 'qualification_artifact_command',
                        lambda root, category, options: ['prepare-input'] if category == 'system' else None)
    calls, active, peak = [], 0, 0
    gate = threading.Lock()
    class FakeControl:
        stopped = threading.Event()
        @contextmanager
        def installed(self, **kwargs):
            yield self
        def run(self, command, *, env, output=None, **kwargs):
            nonlocal active, peak
            if command == ['prepare-input']:
                assert active == 0
                calls.append(('prepare-input', 'host'))
                return 0
            mode, name = command[3:5]
            assert env[vm_selection.VARIABLE] == name
            assert vm_selection.BATCH not in env
            with gate:
                calls.append((mode, name))
                if mode == '--recover':
                    assert active == 0
                    return 0
                assert len([item for item in calls if item[0] == '--recover']) == len(vms)
                active += 1
                peak = max(peak, active)
            assert command[5:] == ['system', 'e2e']
            assert ('prepare-input', 'host') in calls
            time.sleep(.02)
            if name == 'guest-0':
                handoff = tmp_path / 'guest-failure.json'
                handoff.write_text(json.dumps({'categories': ['e2e'], 'failures': [
                    dict(category='e2e', case='E2E-004/terminal', vm='')]}))
                output(f'Failure handoff: {handoff}\n'.encode())
            else:
                output(b'test output\n')
            with gate:
                active -= 1
            return 1 if name == 'guest-0' else 0
    monkeypatch.setattr(queue, 'Control', FakeControl)
    assert queue.run(ROOT, ['all']) == 1
    assert hosts == [['host']]
    assert calls[:len(vms)] == [('--recover', vm.name) for vm in vms]
    assert sorted(name for mode, name in calls if mode == '--execute') == [vm.name for vm in vms]
    assert peak == 2
    evidence, = tmp_path.glob('onpc-vm-queue-*')
    handoff = json.loads((evidence / 'failure.json').read_text())
    assert handoff['categories'] == ['e2e']
    assert handoff['failures'] == [dict(category='e2e', case='E2E-004/terminal', vm='guest-0')]
    assert set(json.loads((evidence / 'results.json').read_text())) == {vm.name for vm in vms}
    for vm in vms:
        text = (evidence / (vm.name + '.log')).read_text()
        assert text.startswith('Failure handoff: ' if vm.name == 'guest-0' else 'test output\n')


def test_cancelling_parallel_workers_waits_for_each_owned_child_cleanup(tmp_path):
    import sys
    import threading
    from regression_process import Control
    from vm_test_queue import dispatch
    vms = [vm_config.VMConfig(f'guest-{index}', Path(f'/disk-{index}'), True) for index in range(5)]
    stopped = threading.Event()
    gate = threading.Lock()
    started = []
    script = tmp_path / 'owned_worker.py'
    script.write_text('import pathlib,sys\nprint("ready", flush=True)\n'
                      'sys.stdin.buffer.readline()\npathlib.Path(sys.argv[1]).write_text("cleaned")\n')
    def execute(vm):
        control = Control()
        control.stopped = stopped
        def output(data):
            if b'ready' in data:
                with gate:
                    started.append(vm.name)
                    if len(started) == 2:
                        stopped.set()
        return control.run([sys.executable, '-B', str(script), str(tmp_path / vm.name)],
                           cwd=tmp_path, env=dict(os.environ), output=output, cooperative=True)
    results = dispatch(vms, 2, execute, stopped)
    assert set(results.values()) == {130}
    assert set(started) == {'guest-0', 'guest-1'}
    assert {path.name for path in tmp_path.iterdir() if path.name != script.name} == set(started)
    assert all((tmp_path / name).read_text() == 'cleaned' for name in started)


def test_both_agent_launchers_bind_the_enabled_queue_and_request_shared_tests(monkeypatch, tmp_path):
    import fix_tests
    import write_e2e
    import vm_selection
    from detached_launcher import atomic
    vms = [vm_config.VMConfig(f'guest-{index}', Path(f'/disk-{index}'), True) for index in range(3)]
    monkeypatch.setattr(vm_config, 'execution', lambda name=None: (2, tuple(vms)))
    monkeypatch.setattr(vm_selection, 'select', lambda name: None)
    selected = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', selected)
    assert fix_tests.main(['system']) == 0
    binding = vm_selection.execution_binding()
    assert binding == {'concurrency': 2, 'vms': [vm.name for vm in vms]}
    monkeypatch.setattr(fix_tests.detached_launcher, 'supervise', lambda *args, **kwargs: args[4])
    command = fix_tests.supervise(ROOT, tmp_path, 42, 'test', 'system', 'model', 'low')
    assert '--vm' not in command
    assert command[1:] == ['--stop-on-error', 'system']
    prompt = fix_tests.repair_prompt('Failure evidence')
    assert 'guest-2' in prompt and 'at most 2 simultaneously' in prompt
    assert 'tools/prepare-appsnapshot --vm NAME --y' in prompt
    monkeypatch.setattr(write_e2e.launcher, 'select', Mock(return_value=(None, False)))
    assert write_e2e.select(ROOT, ['--tasks', '1']) == (None, False)
    arguments = write_e2e.launcher.select.call_args
    assert arguments.kwargs['on_start']
    assert 'tools/prepare-appsnapshot --vm NAME --y' in write_e2e.session_prompt(
        {'task_id': 'TEST', 'phase': 'implement'})
    atomic(tmp_path / 'vm.json', {'vm': binding})
    # Reattachment checks the entire selection, not only the first guest.
    vm_selection.check_binding(tmp_path, binding)
    with pytest.raises(ValueError, match='original'):
        vm_selection.check_binding(tmp_path, dict(binding, vms=['guest-0']))


def test_make_targets_require_configured_vm_and_preserve_literal_name():
    from vm_selection import make_command
    for target in ('system', 'all', 'all-verify', 'appsnapshot'):
        with pytest.raises(ValueError, match='--vm'):
            make_command(ROOT, target, {})
        with pytest.raises(ValueError, match='unknown-vm'):
            make_command(ROOT, target, {'ONPC_MAKE_VM': 'unknown-vm'})
        command = make_command(ROOT, target, {'ONPC_MAKE_VM': vm_name(1)})
        assert command[-2:] == ['--vm', vm_name(1)]


def test_make_watch_observes_all_vms_and_refuses_vm_parameter():
    from vm_selection import make_command
    assert make_command(ROOT, 'watch', {}) == [str(ROOT / 'tools/watch')]
    for name in vm_config.registry():
        with pytest.raises(ValueError, match='VM parameter refused'):
            make_command(ROOT, 'watch', {'ONPC_MAKE_VM': name})
    with pytest.raises(ValueError, match='VM parameter refused'):
        make_command(ROOT, 'watch', {'ONPC_MAKE_VM': '', 'ONPC_WATCH_VM_ORIGIN': 'command line'})


def test_configured_vm_pins_are_selected_by_name_and_missing_pin_never_falls_back():
    import runpy
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    names = list(vm_config.registry())
    uuids = [UUID, '33d86c8c-3b87-4c7b-9520-2df0b7e21e16']
    dispatch.__globals__['VM_UUIDS'] = dict(zip(names, uuids))
    for name, identity in zip(names, uuids):
        command = dispatch(ROOT, ['vm', 'status', '--vm', name])
        assert command[3:7] == ['--vm', name, '--expected-uuid', identity]
    dispatch.__globals__['VM_UUIDS'].pop(names[1])
    with pytest.raises(ValueError, match='prepare-baseline-and-refresh'):
        dispatch(ROOT, ['vm', 'status', '--vm', names[1]])


def test_retained_launcher_binding_requires_original_configured_vm(tmp_path):
    from vm_selection import check_binding, save_binding
    name = vm_name(1)
    save_binding(tmp_path, name)
    check_binding(tmp_path, name)
    for other in (None, vm_name()):
        with pytest.raises(ValueError, match='original --vm NAME'):
            check_binding(tmp_path, other)
