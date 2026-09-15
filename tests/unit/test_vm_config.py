"""Configuration selection and provenance isolation without accessing real VMs."""

import json
import fcntl
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

import prepare_host as host
import prepare_vm as guest
import vm_config
import system_runner as runner
from tests.support.paths import ROOT
from tests.support.vm_baseline import UUID, xml, rig
from tests.support.vm_runner import lease_rig


def write_config(tmp_path, **changes):
    path = tmp_path / 'test-vm.json'
    document = {'name': 'custom-test-vm', 'disk_anchor': '/images/base.qcow2'}
    path.write_text(json.dumps({**document, **changes}))
    return path


def test_shared_config_selects_domain_hostname_disk_and_separate_state(tmp_path):
    configured = vm_config.load(write_config(tmp_path))
    assert configured.name == 'custom-test-vm'
    assert configured.disk_anchor == Path('/images/base.qcow2')
    assert configured.baseline_directory == vm_config.STATE_ROOT / 'custom-test-vm'
    assert host.DOMAIN == guest.HOSTNAME == vm_config.load().name
    assert host.ANCHOR == vm_config.load().disk_anchor
    assert host.BASELINES == vm_config.load().baseline_directory


@pytest.mark.parametrize('changes', [
    {'name': ''}, {'name': '../another'}, {'name': '-flag'}, {'name': 'vm\nname'},
    {'name': 'VM'}, {'name': 'vm..name'}, {'name': 'x' * 64}, {'name': None},
    {'name': []}, {'disk_anchor': 'relative.qcow2'}, {'disk_anchor': '/images/../disk'},
    {'disk_anchor': '/images//disk'}, {'disk_anchor': '/images/disk\n'},
    {'disk_anchor': None}, {'unexpected': True},
])
def test_invalid_config_is_refused_before_resource_access(tmp_path, changes):
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.load(write_config(tmp_path, **changes))


@pytest.mark.parametrize('contents', ['{', '[]', '{}',
    '{"name":"first","name":"second","disk_anchor":"/disk"}'])
def test_malformed_or_ambiguous_configuration_is_refused(tmp_path, contents):
    path = tmp_path / 'test-vm.json'
    path.write_text(contents)
    with pytest.raises(ValueError, match='vm-config:'):
        vm_config.load(path)


def test_missing_configuration_has_no_hardcoded_vm_fallback(tmp_path):
    with pytest.raises(ValueError, match='vm-config:unreadable'):
        vm_config.load(tmp_path / 'absent')


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
    configured = vm_config.load(write_config(tmp_path))
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
