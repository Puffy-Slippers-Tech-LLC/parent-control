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
    vm_control.operate(lease, 'start', [])
    observer = Mock()
    lease.watch = observer
    lease.release()
    observer.detach.assert_called_once()
    observer.close.assert_not_called()
    assert lease.watch is None and lease.fd is None
    assert not lease.source.off
