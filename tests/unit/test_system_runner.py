"""Host-safe guard/transport tests; real temporary files, no live VM operations."""

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest
from test_prepare_host import rig  # Reuse the completed Task 12 mock baseline.

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import system_runner as runner
import system_guest as guest
sys.path.pop(0)

UUID = 'f95890e1-88e7-4779-8ae3-53fdcc34330a'
RUN = 'a' * 32


def test_bootstrap_normalizes_only_official_deb822_archive_uris():
    sources = '''# URIs: http://us.archive.ubuntu.com/ubuntu/
Types: deb deb-src
URIs: http://us.archive.ubuntu.com/ubuntu/ https://vendor.example/repo
 http://security.ubuntu.com/ubuntu
Suites: resolute resolute-updates resolute-backports resolute-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
Enabled: yes

Types: deb
URIs: https://archive.ubuntu.com.evil.example/ubuntu http://archive.ubuntu.com/other
Signed-By:
 http://archive.ubuntu.com/ubuntu/
'''
    expected = sources.replace(
        'URIs: http://us.archive.ubuntu.com/ubuntu/ https://vendor.example/repo',
        'URIs: https://archive.ubuntu.com/ubuntu/ https://vendor.example/repo').replace(
            ' http://security.ubuntu.com/ubuntu\n', ' https://archive.ubuntu.com/ubuntu/\n')
    assert runner.ubuntu_archive_sources(sources) == expected
    assert runner.ubuntu_archive_sources(expected) == expected


@pytest.mark.parametrize('failure', [False, True])
def test_bootstrap_closes_guest_edits_before_install_and_pins_host_key(tmp_path, failure):
    commands, lease, guestfs = Mock(), Mock(), Mock()
    lease.capture.state = {'source': {'layout': {'disk': '/guarded-image'}},
                           'guest': {'preparation_record_sha256': 'e' * 64}}
    lease.state = {'run': RUN, 'baseline_sha256': 'd' * 64}
    lease.source.uuid = UUID
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/package.deb').write_bytes(b'package')
    edit, read = Mock(), Mock()
    guestfs.GuestFS.side_effect = [edit, read]
    for g in (edit, read):
        g.inspect_os.return_value = ['/dev/sda2']
        g.inspect_get_mountpoints.return_value = {'/': '/dev/sda2'}
    files = {
        '/etc/apt/sources.list.d/ubuntu.sources': b'URIs: http://us.archive.ubuntu.com/ubuntu/\n',
        '/etc/fstab': b'/dev/sda2 / ext4 defaults 0 1\nData /Data virtiofs defaults 0 0\n',
        '/etc/machine-id': b'b' * 32,
    }
    edit.read_file.side_effect = files.__getitem__
    read.read_file.return_value = b'ssh-ed25519 test-public-key comment'

    def command(args, **kwargs):
        if args[0] == 'virt-customize':
            edit.close.assert_called_once()
            edit.write.assert_any_call('/etc/apt/sources.list.d/ubuntu.sources',
                                       b'URIs: https://archive.ubuntu.com/ubuntu/\n')
            assert args[args.index('--install') + 1] == 'openssh-server=1:10.2p1-2ubuntu3.6,python3-pytest=9.0.2-4'
            if failure:
                raise runner.CommandError('bootstrap-install-failed')
    commands.run.side_effect = command
    if failure:
        with pytest.raises(runner.CommandError, match='bootstrap-install-failed'):
            runner.bootstrap(commands, lease, tmp_path, guestfs)
        assert guestfs.GuestFS.call_count == 1
    else:
        assert runner.bootstrap(commands, lease, tmp_path, guestfs) == 'ssh-ed25519 test-public-key'
        read.add_drive_opts.assert_called_once_with('/guarded-image', format='qcow2', readonly=True)
        read.mount_ro.assert_called_once_with('/dev/sda2', '/')
        read.close.assert_called_once()


def xml():
    return f'''<domain type="kvm"><name>ubuntu26.04</name><uuid>{UUID}</uuid><devices>
      <disk type="file" device="disk"><driver type="qcow2"/><source file="/image"/><target dev="vda"/></disk>
      <filesystem type="mount"><driver type="virtiofs"/><source dir="/Data"/><target dir="Data"/></filesystem>
      <interface type="network"><source network="default"/></interface>
      <channel type="spicevmc"/><redirdev type="spicevmc"/>
      <graphics type="spice"/><console type="pty"/>
    </devices></domain>'''


def test_isolation_removes_shares_and_spice_transfer_but_preserves_disk():
    root = ET.fromstring(runner.isolated_xml(xml(), UUID, RUN))
    assert root.findtext('uuid') == UUID
    assert root.find('devices/disk/source').get('file') == '/image'
    for name in ('filesystem', 'channel', 'redirdev', 'hostdev'):
        assert not root.findall('devices/' + name)
    assert root.find('devices/graphics/clipboard').get('copypaste') == 'no'
    assert root.find('devices/graphics/filetransfer').get('enable') == 'no'
    assert root.findtext('description') == runner.TAG + RUN


@pytest.mark.parametrize('old,new', [
    ('ubuntu26.04', 'host'), (UUID, 'other'), ('type="qcow2"', 'type="raw"'),
    ('source network="default"', 'source network="bridged"'),
    ('console type="pty"', 'console type="file"'),
    ('</devices>', '<hostdev/></devices>'),
])
def test_refuses_unsupported_or_replaced_vm_layout(old, new):
    with pytest.raises(runner.Error):
        runner.isolated_xml(xml().replace(old, new), UUID, RUN)


def test_active_domain_id_is_required_even_with_same_uuid_and_marker():
    source = Mock()
    layout = runner.baseline.domain_layout(runner.isolated_xml(xml(), UUID, RUN), UUID)
    source.snapshot.return_value = (layout, False)
    domain = source.connection.lookupByName.return_value
    domain.XMLDesc.return_value = runner.isolated_xml(xml(), UUID, RUN)
    domain.ID.return_value = 9
    view = runner.SourceView(source)
    view.run, view.domain_id, view.original_shares = RUN, 8, []
    with pytest.raises(runner.Error, match='domain-replaced'):
        view.snapshot()


def test_source_view_preserves_task12_inventory_contract():
    source = Mock()
    original = runner.baseline.domain_layout(xml(), UUID)
    layout = runner.baseline.domain_layout(runner.isolated_xml(xml(), UUID, RUN), UUID)
    source.snapshot.return_value = (layout, True)
    source.connection.lookupByName.return_value.XMLDesc.return_value = runner.isolated_xml(xml(), UUID, RUN)
    view = runner.SourceView(source)
    view.run, view.original_shares = RUN, original['source_shares']
    assert view.snapshot() == (original, True)


def marker():
    return {'purpose': 'onpc-system-test', 'run': RUN, 'machine_id': 'b' * 32,
            'host_machine_id': 'c' * 32, 'domain_uuid': UUID,
            'baseline_sha256': 'd' * 64, 'preparation_sha256': 'e' * 64,
            'package_sha256': 'f' * 64}


def test_guest_guard_accepts_only_matching_isolated_vm():
    guest.validate_marker(marker(), RUN, 'b' * 32, UUID, ['ext4', 'proc'])


@pytest.mark.parametrize('field,value', [
    ('purpose', 'other'), ('run', 'b' * 32), ('domain_uuid', 'other'),
    ('host_machine_id', 'b' * 32), ('package_sha256', 'invalid'),
    ('machine_id', 'c' * 32),
])
def test_guest_marker_refuses_host_or_replacement(field, value):
    with pytest.raises(guest.GuestError):
        guest.validate_marker(marker() | {field: value}, RUN, 'b' * 32, UUID, ['ext4'])


@pytest.mark.parametrize('filesystem', ['virtiofs', '9p', 'nfs', 'nfs4', 'cifs', 'fuse.sshfs'])
def test_guest_refuses_host_filesystems(filesystem):
    with pytest.raises(guest.GuestError, match='host-filesystem-exposed'):
        guest.validate_marker(marker(), RUN, 'b' * 32, UUID, ['ext4', filesystem])


def test_asset_tree_rejects_symlink_and_special_file(tmp_path):
    root = tmp_path / 'assets'
    root.mkdir()
    path = root / 'link'
    path.symlink_to(tmp_path)
    with pytest.raises(runner.Error, match='special-file'):
        runner.check_tree(root)
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(runner.Error, match='special-file'):
        runner.check_tree(root)


def test_pytest_command_selects_both_required_tests_without_skips():
    before = runner.pytest_command(RUN, 'installed')
    after = runner.pytest_command(RUN, 'rebooted')
    assert 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1' in before
    assert before[-1].endswith('::test_first_install_requests_reboot')
    assert after[-1].endswith('::test_reboot_applies_installation')
    assert before[-2] == after[-2]
    assert before[-2].endswith('::test_installed_package')
    assert runner.guest_command(RUN, 'install')[-2:] == [runner.PAYLOAD + '/system_guest.py', 'install']


def test_readiness_timeout_is_bounded_without_fixed_sleep(monkeypatch):
    source = Mock()
    source.domain.interfaceAddresses.return_value = {}
    clock = iter([0, 0, 2, 2])
    monkeypatch.setattr(runner.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(runner.threading, 'Event', Mock)
    with pytest.raises(runner.Error, match='readiness-timeout'):
        runner.address(source, timeout=1)
    source.api.virEventRemoveTimeout.assert_called_once()


def test_install_assertion_failure_collects_evidence_without_reboot_or_retry(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    failure = runner.CommandError('test-assertion-failed')
    vm.call.side_effect = [b'', failure, b'']
    with pytest.raises(runner.CommandError, match='test-assertion-failed'):
        runner.installed_run(vm, lease, tmp_path)
    assert vm.call.call_count == 3
    assert vm.call.call_args.args[0] == runner.guest_command(RUN, 'collect', 'failed')
    vm.reboot.assert_not_called()
    assert vm.copy.call_args.args[0] is True


def test_collection_failure_does_not_hide_original_connection_failure(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    vm.ready.side_effect = runner.CommandError('original-connection-failed')
    vm.call.side_effect = runner.CommandError('collection-failed')
    with pytest.raises(runner.CommandError, match='original-connection-failed'):
        runner.installed_run(vm, lease, tmp_path)
    vm.reboot.assert_not_called()


@pytest.mark.parametrize('skipped', [0, 1])
def test_both_pytest_phases_must_supply_complete_unskipped_evidence(tmp_path, skipped):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    output = tmp_path / 'guest-results'
    output.mkdir()
    for phase in ('installed', 'rebooted'):
        (output / f'{phase}.xml').write_text(
            f'<testsuites><testsuite tests="2" failures="0" errors="0" skipped="{skipped}"/></testsuites>')
    if skipped:
        with pytest.raises(runner.Error, match='missing-failed-or-skipped-tests'):
            runner.installed_run(vm, lease, tmp_path)
    else:
        runner.installed_run(vm, lease, tmp_path)
    vm.reboot.assert_called_once()
    assert vm.call.call_count == 5
    assert vm.call.call_args_list[2].args[0] == runner.guest_command(RUN, 'collect', 'installed')


def test_restore_never_requests_boot_or_deletes_snapshot():
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.capture.revalidate = Mock()
    lease.snapshot_xml = 'snapshot'
    snapshot = lease.source.domain.snapshotLookupByName.return_value
    snapshot.getXMLDesc.return_value = 'snapshot'
    lease.restore()
    lease.source.domain.revertToSnapshot.assert_called_once_with(snapshot, 0)
    snapshot.delete.assert_not_called()
    lease.source.domain.create.assert_not_called()


def test_restore_refuses_changed_snapshot():
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.capture.revalidate = Mock()
    lease.snapshot_xml = 'snapshot'
    lease.source.domain.snapshotLookupByName.return_value.getXMLDesc.return_value = 'replaced'
    with pytest.raises(runner.Error, match='snapshot-metadata-changed'):
        lease.restore()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_libvirt_shutting_down_is_active_not_offline():
    api = Mock(VIR_DOMAIN_RUNNING=1, VIR_DOMAIN_SHUTDOWN=4, VIR_DOMAIN_SHUTOFF=5,
               VIR_DOMAIN_XML_INACTIVE=2)
    connection = api.open.return_value
    connection.getURI.return_value = runner.baseline.URI
    domain = connection.lookupByName.return_value
    domain.UUIDString.return_value = UUID
    domain.isPersistent.return_value = True
    domain.hasManagedSaveImage.return_value = False
    domain.state.return_value = (4, 0)
    domain.XMLDesc.return_value = xml()
    domain.blockJobInfo.return_value = {}
    source = runner.baseline.LibvirtSource(api)
    assert source.snapshot()[1] is False
    domain.blockJobInfo.assert_called_once()


@pytest.fixture
def lease_rig(rig):
    rig.capture().run()
    source = rig.source
    original = __import__('test_prepare_host').xml(rig.top)
    original = original.replace('</devices>', '<interface type="network"><source network="default"/></interface></devices>')
    current = {'xml': original, 'id': -1}
    source.api = Mock(VIR_DOMAIN_XML_INACTIVE=2)
    source.uuid = UUID
    source.domain = Mock()
    source.connection = Mock()
    source.domain.XMLDesc.side_effect = lambda *_: current['xml']
    source.domain.ID.side_effect = lambda: current['id']
    source.domain.autostart.return_value = False
    source.connection.lookupByName.return_value = source.domain

    def define(value):
        current['xml'] = value
        source.layout = runner.baseline.domain_layout(value, UUID)
    source.connection.defineXML.side_effect = define

    def start():
        source.off, current['id'] = False, 71
    source.domain.create.side_effect = start
    snapshot = source.domain.snapshotLookupByName.return_value
    snapshot.getXMLDesc.side_effect = lambda *_: source.baseline_xml

    def restore(*_):
        source.off, current['id'] = True, -1
        define(original)
    source.domain.revertToSnapshot.side_effect = restore
    source.domain.destroyFlags.side_effect = restore
    return runner.Lease(source, rig.commands, rig.inspect, directory=rig.directory, anchor=rig.anchor), current


def test_full_lease_preserves_baseline_and_restores_original_config(lease_rig):
    lease, current = lease_rig
    baseline_xml = lease.source.baseline()
    with lease:
        original = lease.original_xml
        lease.prepare()
        assert not lease.source.layout['source_shares']
        lease.start()
        assert lease.view.domain_id == 71
    assert lease.state['phase'] == 'complete'
    assert lease.source.off
    assert current['xml'] == original
    assert lease.source.baseline() == baseline_xml
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert lease.fd is None


def test_interruption_restores_owned_vm_and_preserves_failure(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(KeyboardInterrupt):
        with lease:
            lease.prepare()
            lease.start()
            raise KeyboardInterrupt
    assert lease.state['phase'] == 'complete'
    assert lease.source.off


def test_busy_lease_refuses_without_vm_mutation(lease_rig):
    lease, _ = lease_rig
    with lease:
        another = runner.Lease(lease.source, lease.commands, lease.inspect,
                               directory=lease.directory, anchor=lease.capture.anchor)
        with pytest.raises(runner.Error, match='busy-controller'):
            another.__enter__()
        lease.source.domain.create.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()


def test_unfinished_journal_refuses_before_vm_mutation(lease_rig):
    lease, _ = lease_rig
    lease.journal.write_text('{"phase":"running"}')
    lease.journal.chmod(0o600)
    with pytest.raises(runner.Error, match='interrupted-run'):
        lease.__enter__()
    assert lease.fd is None
    lease.source.domain.create.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_snapshot_changed_during_run_leaves_recovery_evidence(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(runner.Error, match='snapshot-metadata-changed'):
        with lease:
            lease.prepare()
            lease.start()
            lease.source.baseline_xml += ' '
    assert lease.state['phase'] == 'cleanup-requested'
    assert lease.fd is None
    # Initial restore only; no revert or force stop against the changed identity.
    assert lease.source.domain.revertToSnapshot.call_count == 1
    lease.source.domain.destroyFlags.assert_not_called()
