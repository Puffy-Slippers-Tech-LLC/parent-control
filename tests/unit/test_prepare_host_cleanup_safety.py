"""Isolated ownership regressions; no real process is terminated here."""

import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests/integration"))
import prepare_host as host
sys.path.pop(0)


@pytest.mark.parametrize("failure", [KeyboardInterrupt, subprocess.TimeoutExpired("qemu-img", 1)])
@pytest.mark.parametrize("needs_kill", [False, True])
def test_only_directly_spawned_pidfd_is_signalled(failure, needs_kill):
    child = Mock(pid=98765, returncode=0)
    child.communicate.side_effect = failure
    child.wait.side_effect = [subprocess.TimeoutExpired("qemu-img", 10), 0] if needs_kill else [0]
    context = Mock()
    context.__enter__ = Mock(return_value=child)
    context.__exit__ = Mock(return_value=False)
    with patch.object(host.subprocess, "Popen", return_value=context) as spawn, \
            patch.object(host.os, "pidfd_open", return_value=42) as pin, \
            patch.object(host.signal, "pidfd_send_signal") as send, \
            patch.object(host.os, "close") as close:
        commands = host.Commands()
        commands.lock_fd = 77
        with pytest.raises((KeyboardInterrupt, subprocess.TimeoutExpired)):
            commands.run(["qemu-img", "info"])
    pin.assert_called_once_with(98765)
    assert send.call_args_list[0].args == (42, signal.SIGTERM)
    assert send.call_count == (2 if needs_kill else 1)
    if needs_kill:
        assert send.call_args_list[1].args == (42, signal.SIGKILL)
    assert spawn.call_args.kwargs["pass_fds"] == (77,)
    close.assert_called_once_with(42)


def test_exited_child_cannot_turn_into_pid_based_signal():
    child = Mock(pid=98765, returncode=0)
    child.communicate.side_effect = KeyboardInterrupt
    context = Mock(__enter__=Mock(return_value=child), __exit__=Mock(return_value=False))
    with patch.object(host.subprocess, "Popen", return_value=context), \
            patch.object(host.os, "pidfd_open", return_value=42), \
            patch.object(host.signal, "pidfd_send_signal", side_effect=ProcessLookupError) as send, \
            patch.object(host.os, "close"), patch.object(host.os, "kill") as raw_kill:
        with pytest.raises(KeyboardInterrupt):
            host.Commands().run(["qemu-img", "info"])
    send.assert_called_once_with(42, signal.SIGTERM)
    raw_kill.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()
