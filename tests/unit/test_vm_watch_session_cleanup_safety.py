"""The maintenance keeper cannot signal/adopt a VM or an unrecorded process."""

import signal
import socket
import subprocess
import threading
from unittest.mock import Mock, patch

import pytest

import vm_watch_session as session
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig


def handle():
    item = session.Session.__new__(session.Session)
    item.control = Mock()
    item.child = Mock(pid=12345)
    item.pidfd = 42
    return item


def test_detach_preserves_collector_without_signalling():
    item = handle()
    child, control = item.child, item.control
    with patch.object(session.os, 'close') as close, \
            patch.object(session.signal, 'pidfd_send_signal') as send:
        item.detach()
    control.sendall.assert_called_once_with(b'detach')
    control.close.assert_called_once()
    close.assert_called_once_with(42)
    child.wait.assert_not_called()
    send.assert_not_called()
    assert item.control is item.child is item.pidfd is None


def test_keeper_retains_its_log_storage_until_it_exits(tmp_path, monkeypatch):
    import tools.test_storage as storage
    import vm_config
    adapter = Mock(run='a' * 32)
    adapter.lease.commands.directory = tmp_path
    adapter.lease.source.domain.XMLDesc.return_value = '<domain><devices/></domain>'
    display = adapter.open_display.return_value
    display.fileno.return_value = 101
    local, remote = Mock(), Mock()
    local.recv.return_value = b'ready'
    remote.fileno.return_value = 102
    monkeypatch.setattr(storage, 'scratch_descriptors', lambda: (103,))
    monkeypatch.setattr(vm_config, 'arguments', lambda: [])
    with patch.object(session.socket, 'socketpair', return_value=(local, remote)), \
            patch.object(session.subprocess, 'Popen') as spawn, \
            patch.object(session.os, 'pidfd_open', return_value=42), \
            patch.object(session.os, 'close'):
        item = session.Session(adapter, 1000)
        assert spawn.call_args.kwargs['pass_fds'] == (102, 101, 103)
        item.detach()
    spawn.return_value.wait.assert_not_called()


@pytest.mark.parametrize('pinned', [False, True])
def test_keeper_cleanup_only_signals_its_pinned_child(pinned):
    item = handle()
    if not pinned:
        item.pidfd = None
    child = item.child
    child.wait.side_effect = [subprocess.TimeoutExpired('keeper', 8), 0]
    with patch.object(session.os, 'close'), patch.object(session.os, 'kill') as raw, \
            patch.object(session.signal, 'pidfd_send_signal') as send:
        if pinned:
            item.close()
            send.assert_called_once_with(42, signal.SIGKILL)
        else:
            with pytest.raises(ValueError, match='unrecorded-session'):
                item.close()
            send.assert_not_called()
            assert item.child is child
    raw.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()


@pytest.mark.parametrize('detach', [False, True])
def test_keeper_survives_only_explicit_handoff_and_stops_on_identity_loss(detach):
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    observer = Mock(finished=threading.Event())
    guard = Mock(side_effect=[True, True, False])
    with server, client:
        if detach:
            client.sendall(b'detach')
        client.close()
        session.follow(server, observer, guard)
    assert guard.call_count == (3 if detach else 1)
    if detach:
        assert observer.lease_locked is False
    observer.close.assert_not_called()  # Owning finally performs the one reap.


@pytest.mark.parametrize('change', [None, 'uri', 'uuid', 'instance', 'xml'])
def test_keeper_revalidation_never_adopts_or_controls_guest(change):
    connection = Mock()
    connection.getURI.return_value = 'qemu:///session' if change == 'uri' else 'qemu:///system'
    domain = connection.lookupByUUIDString.return_value
    domain.UUIDString.return_value = 'other' if change == 'uuid' else 'pinned'
    domain.ID.return_value = 72 if change == 'instance' else 71
    xml = '<domain><devices/></domain>'
    domain.XMLDesc.return_value = '<domain><devices><disk/></devices></domain>' if change == 'xml' else xml
    digest = session.configuration_digest(xml)
    if change == 'uri':
        with pytest.raises(ValueError, match='session-connection'):
            session.matches(connection, 'pinned', 71, digest)
    else:
        assert session.matches(connection, 'pinned', 71, digest) == (change is None)
    domain.create.assert_not_called()
    domain.destroyFlags.assert_not_called()
    domain.openGraphicsFD.assert_not_called()


def test_boot_memory_report_keeps_viewing_without_ignoring_configuration():
    connection = Mock()
    connection.getURI.return_value = 'qemu:///system'
    domain = connection.lookupByUUIDString.return_value
    domain.UUIDString.return_value, domain.ID.return_value = 'pinned', 71
    xml = ('<domain><memory unit="KiB">2048</memory>'
           '<currentMemory unit="KiB">1024</currentMemory>'
           '<description>owned</description><devices><disk source="attested"/>'
           '<graphics type="dbus"/></devices></domain>')
    digest = session.configuration_digest(xml)
    domain.XMLDesc.return_value = xml.replace('>1024<', '>512<')
    assert session.matches(connection, 'pinned', 71, digest)
    for original, replacement in [('>2048<', '>4096<'), ('currentMemory unit="KiB"', 'currentMemory unit="MiB"'),
                                  ('>owned<', '>foreign<'), ('source="attested"', 'source="replaced"'),
                                  ('type="dbus"', 'type="vnc"')]:
        domain.XMLDesc.return_value = xml.replace(original, replacement)
        assert not session.matches(connection, 'pinned', 71, digest)
    domain.XMLDesc.return_value = xml.replace('>1024<', '>invalid<')
    with pytest.raises(ValueError, match='session-memory-report'):
        session.matches(connection, 'pinned', 71, digest)


def test_maintenance_release_detaches_and_releases_controller_lock(lease_rig):
    import vm_control
    lease, _ = lease_rig
    # SSH bootstrap is outside this simulated lease/watch ownership check.
    with patch('vm_probe.prepare_maintenance_transport'):
        vm_control.operate(lease, 'start', [])
    observer = Mock()
    lease.watch = observer
    lease.release()
    observer.detach.assert_called_once()
    observer.close.assert_not_called()
    assert lease.watch is None and lease.fd is None
    assert not lease.source.off


def test_carrier_renewal_keeps_viewing_but_network_identity_remains_bound():
    connection = Mock()
    connection.getURI.return_value = 'qemu:///system'
    domain = connection.lookupByUUIDString.return_value
    domain.UUIDString.return_value, domain.ID.return_value = 'pinned', 71
    xml = ('<domain><devices><interface type="network">'
           '<mac address="52:54:00:11:22:33"/><source network="default"/>'
           '<model type="virtio"/></interface></devices></domain>')
    digest = session.configuration_digest(xml)
    for state in ('down', 'up'):
        domain.XMLDesc.return_value = xml.replace('</interface>', f'<link state="{state}"/></interface>')
        assert session.matches(connection, 'pinned', 71, digest)
    domain.XMLDesc.return_value = xml.replace('network="default"',
        'portid="runtime-port" network="default"')
    assert session.matches(connection, 'pinned', 71, digest)
    for original, replacement in [('network="default"', 'network="other"'),
            ('52:54:00:11:22:33', '52:54:00:11:22:44'), ('type="virtio"', 'type="e1000"')]:
        domain.XMLDesc.return_value = xml.replace(original, replacement)
        assert not session.matches(connection, 'pinned', 71, digest)
    for link in ('<link state="invalid"/>', '<link state="up" extra="ignored"/>',
                 '<link state="up"><other/></link>', '<link state="up"/><link state="down"/>'):
        with pytest.raises(ValueError, match='session-network-link'):
            session.configuration_digest(xml.replace('</interface>', link + '</interface>'))


def test_guest_agent_reconnection_keeps_viewing_but_channel_identity_remains_bound():
    connection = Mock()
    connection.getURI.return_value = 'qemu:///system'
    domain = connection.lookupByUUIDString.return_value
    domain.UUIDString.return_value, domain.ID.return_value = 'pinned', 71
    xml = ('<domain><devices><channel type="spicevmc">'
           '<target type="virtio" name="com.redhat.spice.0" state="disconnected"/>'
           '<address type="virtio-serial" controller="0" port="1"/>'
           '</channel></devices></domain>')
    digest = session.configuration_digest(xml)
    for replacement in ('state="connected"', ''):
        domain.XMLDesc.return_value = xml.replace('state="disconnected"', replacement)
        assert session.matches(connection, 'pinned', 71, digest)
    for original, replacement in [('type="spicevmc"', 'type="unix"'),
            ('name="com.redhat.spice.0"', 'name="other"'),
            ('port="1"', 'port="2"'), ('type="virtio"', 'type="guestfwd"')]:
        domain.XMLDesc.return_value = xml.replace(original, replacement)
        assert not session.matches(connection, 'pinned', 71, digest)
    with pytest.raises(ValueError, match='session-channel-state'):
        session.configuration_digest(xml.replace('state="disconnected"', 'state="invalid"'))
