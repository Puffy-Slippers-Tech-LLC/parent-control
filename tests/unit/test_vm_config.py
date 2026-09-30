"""Configuration selection and provenance isolation without accessing real VMs."""

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


def test_configured_vm_name_has_no_literal_in_tooling_or_documentation():
    configured = vm_config.selected()
    # The configured display name belongs in config, not its consumers.
    name = configured.name
    for directory in ('tools', 'tests/integration', 'docs'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and path.suffix in ('', '.py', '.md', '.MD', '.json', '.rules', '.sh'):
                assert name not in path.read_text(), str(path.relative_to(ROOT))


def test_configuration_change_invalidates_guest_preparation_digest(tmp_path):
    for relative in guest.SCRIPT_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / relative).read_bytes())
    before = guest.preparation_digest(tmp_path)
    (tmp_path / 'config/test-vm.json').write_text(
        '{"name":"different-vm","disk_anchor":"/images/base.qcow2"}')
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


def test_names_share_legacy_lock_and_refuse_concurrent_capture(rig, monkeypatch):
    state_root = rig.directory.parent
    monkeypatch.setattr(vm_config, 'STATE_ROOT', state_root)
    capture = rig.capture()
    capture.run()
    other_directory = state_root / 'another-vm'
    other_directory.mkdir(mode=0o700)
    other = host.Capture(rig.source, rig.commands, rig.inspect,
                         anchor=rig.anchor, directory=other_directory)
    assert capture.lock_path == other.lock_path == state_root / '.lock'
    with capture.lock_path.open('rb') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        for controller in (capture, other):
            with pytest.raises(host.CaptureError, match='busy-controller'):
                controller.run()
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
    assert configured['onpc-Fedora-Workstation-44'].disk_anchor == Path(
        '/Data/virt-manager/onpc-Fedora-Workstation-44.qcow2')
    assert 'onpc-Ubuntu26.04' in configured


@pytest.mark.parametrize('name', [None, '', 'unknown-vm', 'onpc-fedora-workstation-44'])
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
    ['--vm', 'onpc-Ubuntu26.04', '--vm', 'onpc-Fedora-Workstation-44']])
def test_cli_selection_has_no_environment_or_default_fallback(argv):
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.extract(argv)


def test_selection_updates_imported_controller_and_guest(monkeypatch):
    configured = vm_config.select('onpc-Fedora-Workstation-44')
    assert host.DOMAIN == configured.name
    assert host.ANCHOR == configured.disk_anchor
    assert host.BASELINES == configured.baseline_directory
    assert guest.HOSTNAME == configured.hostname
    assert host.BASELINES != vm_config.load('onpc-Ubuntu26.04').baseline_directory


@pytest.mark.parametrize('command', [
    ['tools/test-vm', 'status'], ['tools/prepare-baseline', '--mode', 'auto'],
    ['tools/prepare-appsnapshot'], ['tools/cleanup-e2e'],
    ['tools/run-tests', 'system'], ['tools/run-tests', 'e2e'],
    ['tools/run-tests', 'integration', 'check_test_recovery'],
    ['tools/run-tests', 'all'], ['tools/write-e2e', '--tasks', '1'],
    ['tools/fix-tests', 'system'],
])
@pytest.mark.parametrize('options', [[], ['--vm', 'unknown-vm']])
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


def test_make_targets_require_configured_vm_and_preserve_literal_name():
    from vm_selection import make_command
    for target in ('system', 'all', 'all-verify', 'appsnapshot'):
        with pytest.raises(ValueError, match='--vm'):
            make_command(ROOT, target, {})
        with pytest.raises(ValueError, match='unknown-vm'):
            make_command(ROOT, target, {'ONPC_MAKE_VM': 'unknown-vm'})
        command = make_command(ROOT, target, {'ONPC_MAKE_VM': 'onpc-Fedora-Workstation-44'})
        assert command[-2:] == ['--vm', 'onpc-Fedora-Workstation-44']


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
    name = 'onpc-Fedora-Workstation-44'
    save_binding(tmp_path, name)
    check_binding(tmp_path, name)
    for other in (None, 'onpc-Ubuntu26.04'):
        with pytest.raises(ValueError, match='original --vm NAME'):
            check_binding(tmp_path, other)
