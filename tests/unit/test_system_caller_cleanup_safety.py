"""Mocked prerequisite before persistent callers may run in the test VM."""

import signal
import subprocess
from unittest.mock import Mock

import pytest

import system_caller as caller


def rig(monkeypatch):
    child = Mock(pid=24680)
    monkeypatch.setattr(caller.guest, 'guard', Mock())
    monkeypatch.setattr(caller.subprocess, 'Popen', Mock(return_value=child))
    monkeypatch.setattr(caller.os, 'pidfd_open', Mock(return_value=42))
    monkeypatch.setattr(caller.os, 'close', Mock())
    monkeypatch.setattr(caller.signal, 'pidfd_send_signal', Mock())
    monkeypatch.setattr(caller.os, 'kill', Mock())
    monkeypatch.setattr(caller.PersistentCaller, 'receive', Mock(return_value={
        'uid': 1234, 'name': ':1.234'}))
    return child


@pytest.mark.parametrize('already_exited', [False, True])
def test_cleanup_signals_only_direct_child_pidfd(monkeypatch, already_exited):
    child = rig(monkeypatch)
    child.wait.side_effect = [subprocess.TimeoutExpired('caller', 2), 0]
    if already_exited:
        caller.signal.pidfd_send_signal.side_effect = ProcessLookupError
    instance = caller.PersistentCaller(1234)
    instance.close()
    instance.close()
    caller.os.pidfd_open.assert_called_once_with(child.pid)
    caller.signal.pidfd_send_signal.assert_called_once_with(42, signal.SIGKILL)
    caller.os.close.assert_called_once_with(42)
    caller.os.kill.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()


def test_normal_eof_needs_no_signal(monkeypatch):
    child = rig(monkeypatch)
    with caller.PersistentCaller(1234):
        pass
    child.stdin.close.assert_called_once()
    caller.signal.pidfd_send_signal.assert_not_called()
    caller.os.close.assert_called_once_with(42)


def test_missing_identity_pin_never_signals_numeric_pid(monkeypatch):
    child = rig(monkeypatch)
    caller.os.pidfd_open.side_effect = OSError('pin unavailable')
    with pytest.raises(OSError):
        caller.PersistentCaller(1234)
    child.stdin.close.assert_called_once()
    child.wait.assert_called_once_with(timeout=5)
    caller.signal.pidfd_send_signal.assert_not_called()
    caller.os.kill.assert_not_called()
    child.kill.assert_not_called()


def test_guard_failure_prevents_spawn(monkeypatch):
    rig(monkeypatch)
    caller.guest.guard.side_effect = caller.guest.GuestError('guard-failed')
    with pytest.raises(caller.guest.GuestError):
        caller.PersistentCaller(1234)
    caller.subprocess.Popen.assert_not_called()


@pytest.mark.parametrize('failure', [KeyboardInterrupt(), caller.guest.GuestError('bad-ready')])
def test_initialization_failure_closes_owned_caller(monkeypatch, failure):
    child = rig(monkeypatch)
    caller.PersistentCaller.receive.side_effect = failure
    with pytest.raises(type(failure)):
        caller.PersistentCaller(1234)
    child.stdin.close.assert_called_once()
    caller.os.close.assert_called_once_with(42)
