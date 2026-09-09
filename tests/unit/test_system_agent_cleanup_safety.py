"""Mocked prerequisite for the real guest authentication agent."""

import signal
import subprocess
from unittest.mock import Mock, call
from types import SimpleNamespace

import pytest

import system_caller as caller


def subject():
    return SimpleNamespace(name=':1.234', uid=2345, agent_subject=lambda: '12345,67890')


def rig(monkeypatch):
    child = Mock(pid=24680, returncode=None)
    child.poll.return_value = None
    for name, replacement in (
        ('openpty', Mock(return_value=(10, 11))),
        ('pipe', Mock(return_value=(12, 13))),
        ('pidfd_open', Mock(return_value=42)),
        ('read', Mock(return_value=b'')),
        ('close', Mock()), ('kill', Mock()),
    ):
        monkeypatch.setattr(caller.os, name, replacement)
    monkeypatch.setattr(caller.guest, 'guard', Mock())
    monkeypatch.setattr(caller.subprocess, 'Popen', Mock(return_value=child))
    monkeypatch.setattr(caller.select, 'select', Mock(return_value=([12], [], [])))
    monkeypatch.setattr(caller.signal, 'pidfd_send_signal', Mock())
    return child


@pytest.mark.parametrize('exited', [False, True])
def test_agent_signals_only_pinned_direct_child(monkeypatch, exited):
    child = rig(monkeypatch)
    if exited:
        caller.signal.pidfd_send_signal.side_effect = ProcessLookupError
    agent = caller.TextAgent(subject())
    agent.close()
    agent.close()
    caller.os.pidfd_open.assert_called_once_with(child.pid)
    caller.signal.pidfd_send_signal.assert_called_once_with(42, signal.SIGTERM)
    caller.os.kill.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()
    assert caller.os.close.call_args_list.count(call(42)) == 1
    assert caller.os.close.call_args_list.count(call(10)) == 1


def test_agent_timeout_escalates_same_pin(monkeypatch):
    child = rig(monkeypatch)
    child.wait.side_effect = [subprocess.TimeoutExpired('agent', 5), 0, 0]
    with caller.TextAgent(subject()):
        pass
    assert caller.signal.pidfd_send_signal.call_args_list == [
        call(42, signal.SIGTERM), call(42, signal.SIGKILL)]


def test_agent_missing_pin_never_signals(monkeypatch):
    child = rig(monkeypatch)
    caller.os.pidfd_open.side_effect = OSError('pin unavailable')
    with pytest.raises(OSError):
        caller.TextAgent(subject())
    caller.signal.pidfd_send_signal.assert_not_called()
    caller.os.kill.assert_not_called()
    child.kill.assert_not_called()
    for fd in (10, 11, 12, 13):
        assert caller.os.close.call_args_list.count(call(fd)) == 1


def test_agent_registration_failure_cleans_pinned_process(monkeypatch):
    rig(monkeypatch)
    caller.select.select.return_value = ([], [], [])
    with pytest.raises(caller.guest.GuestError, match='agent:registration'):
        caller.TextAgent(subject())
    caller.signal.pidfd_send_signal.assert_called_once_with(42, signal.SIGTERM)


def test_agent_guard_prevents_spawn(monkeypatch):
    rig(monkeypatch)
    caller.guest.guard.side_effect = caller.guest.GuestError('guard')
    with pytest.raises(caller.guest.GuestError):
        caller.TextAgent(subject())
    caller.subprocess.Popen.assert_not_called()


def test_password_diagnostic_representation_is_redacted():
    password = caller.FixturePassword()
    assert password._value.decode() not in repr(password)
    assert password._value.decode() not in str(password)
