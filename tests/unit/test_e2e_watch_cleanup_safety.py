"""Collector cleanup can signal only its pinned child, never user viewers."""

import signal
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import e2e_watch as watch
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig


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


@pytest.mark.parametrize('graphics', ['vnc', 'spice'])
@pytest.mark.parametrize('failure', [None, 'body', 'close'])
def test_every_lease_observes_start_and_owns_cleanup(lease_rig, graphics, failure):
    lease, _ = lease_rig
    observer = Mock()
    lease.view.graphics_type = graphics
    with patch.dict(watch.os.environ, {'PKEXEC_UID': '1000'}), \
            patch.object(watch, 'os', SimpleNamespace(geteuid=lambda: 0, environ=watch.os.environ)), \
            patch.object(watch, 'DisplayAdapter') as adapter, \
            patch.object(watch, 'start', return_value=observer):
        lease.__enter__()
        lease.prepare()
        try:
            lease.start()
            assert lease.watch is observer
            adapter.assert_called_once_with(lease.source, lease.view.domain_id,
                                            lease.guard, lease.state['run'], lease=lease)
            if failure == 'close':
                observer.close.side_effect = RuntimeError('collector-cleanup-failed')
                with pytest.raises(RuntimeError, match='collector-cleanup-failed'):
                    lease.close_watch()
                assert lease.watch is observer  # Retain identity for retry.
                observer.close.side_effect = None
            elif failure == 'body':
                with pytest.raises(RuntimeError, match='body-failed'):
                    try:
                        raise RuntimeError('body-failed')
                    finally:
                        lease.close_watch()
                assert lease.watch is None
            lease.stop()
            assert lease.watch is None
            observer.close.assert_called()
        finally:
            lease.finish()
            lease.release()


def test_failed_shared_start_cannot_swallow_collector_cleanup_failure():
    lease = Mock(watch=None, state={'run': 'a' * 32})
    with patch.dict(watch.os.environ, {'PKEXEC_UID': '1000'}), \
            patch.object(watch.os, 'geteuid', return_value=0), \
            patch.object(watch, 'DisplayAdapter'), patch.object(watch, 'start',
                side_effect=RuntimeError('collector-cleanup-failed')):
        with pytest.raises(RuntimeError, match='collector-cleanup-failed'):
            watch.attach(lease)
