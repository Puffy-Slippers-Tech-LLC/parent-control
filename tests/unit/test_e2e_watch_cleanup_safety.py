"""Collector cleanup can signal only its pinned child, never user viewers."""

import signal
import subprocess
import threading
from unittest.mock import Mock, patch

import pytest

import e2e_watch as watch


def handle():
    item = watch.Observer.__new__(watch.Observer)
    item.display, item.listener, item.control = Mock(), Mock(), Mock()
    item.child, item.pidfd, item.publication = Mock(pid=12345), 42, Mock()
    item.thread = None
    item.stop = threading.Event()
    return item


@pytest.mark.parametrize('expired', [False, True])
def test_cleanup_revokes_owned_sockets_before_pinned_signal(expired):
    item = handle()
    child = item.child
    child.wait.side_effect = [subprocess.TimeoutExpired('collector', 2), 0]
    events = []
    for peer in (item.display, item.listener, item.control):
        peer.shutdown.side_effect = lambda *_: events.append('revoke')
    def send(*_):
        assert events == ['revoke'] * 3
        if expired:
            raise ProcessLookupError
    with patch.object(watch.signal, 'pidfd_send_signal', side_effect=send) as pinned, \
            patch.object(watch.os, 'kill') as raw, patch.object(watch.os, 'close') as close:
        item.close()
    pinned.assert_called_once_with(42, signal.SIGKILL)
    raw.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()
    close.assert_called_once_with(42)


def test_unrecorded_identity_never_signals_numeric_pid():
    item = handle()
    item.pidfd = None
    item.child.wait.side_effect = subprocess.TimeoutExpired('collector', 2)
    with patch.object(watch.signal, 'pidfd_send_signal') as pinned, \
            patch.object(watch.os, 'kill') as raw:
        with pytest.raises(ValueError, match='unrecorded-collector'):
            item.close()
    pinned.assert_not_called()
    raw.assert_not_called()


def test_unfinished_cleanup_retains_identity():
    item = handle()
    item.child.wait.side_effect = subprocess.TimeoutExpired('collector', 2)
    with patch.object(watch.signal, 'pidfd_send_signal'), patch.object(watch.os, 'close') as close:
        with pytest.raises(subprocess.TimeoutExpired):
            item.close()
    assert item.pidfd == 42
    close.assert_not_called()


def test_failed_pin_closes_gate_without_authorizing_attachment():
    display = Mock()
    local, remote, listener, listener_remote = Mock(), Mock(), Mock(), Mock()
    with patch.object(watch, 'Publication'), \
            patch.object(watch.socket, 'socketpair', side_effect=[(local, remote), (listener, listener_remote)]), \
            patch.object(watch.subprocess, 'Popen') as spawn, \
            patch.object(watch.os, 'pidfd_open', side_effect=OSError), \
            patch.object(watch.signal, 'pidfd_send_signal') as send:
        with pytest.raises(OSError):
            watch.Observer(display, 1000, 'a' * 32)
    local.sendall.assert_not_called()
    local.close.assert_called_once()
    spawn.return_value.wait.assert_called_once_with(timeout=2)
    send.assert_not_called()


def test_optional_failure_keeps_automation_running():
    adapter = Mock(run='a' * 32)
    with patch.dict(watch.os.environ, {'PKEXEC_UID': '1000'}), \
            patch.object(watch, 'Observer', side_effect=ValueError('unavailable')):
        assert watch.start(adapter) is None
    adapter.open_display.assert_called_once_with(index=1)
    adapter.close_display.assert_not_called()
    adapter.lease.stop.assert_not_called()


@pytest.mark.parametrize('failure', [None, 'body', 'close'])
def test_setup_display_closes_its_observer_without_vm_lifecycle(failure):
    lease, observer = Mock(), Mock()
    if failure == 'close':
        observer.close.side_effect = RuntimeError('cleanup-failed')
    with patch('graphical_lease.Adapter') as adapter, patch.object(watch, 'start', return_value=observer):
        def invoke():
            with watch.running_display(lease):
                if failure == 'body':
                    raise RuntimeError('body-failed')
        if failure:
            with pytest.raises(RuntimeError):
                invoke()
        else:
            invoke()
    adapter.assert_called_once_with(lease, running=True)
    observer.close.assert_called_once()
    lease.start.assert_not_called()
    lease.stop.assert_not_called()


def test_failed_setup_display_start_cannot_swallow_collector_cleanup_failure():
    with patch('graphical_lease.Adapter'), patch.object(watch, 'start',
            side_effect=RuntimeError('collector-cleanup-failed')):
        with pytest.raises(RuntimeError, match='collector-cleanup-failed'):
            with watch.running_display(Mock()):
                pytest.fail('Cannot proceed past unfinished collector cleanup')
