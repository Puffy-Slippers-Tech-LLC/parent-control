"""Refusal paths may signal only the exact Popen child created by capture."""

import subprocess
from unittest.mock import Mock

import pytest
from tests.support import terminal


@pytest.mark.parametrize("failure", ["spawn", "timeout", "read", "wait", "interrupt"])
def test_capture_closes_descriptors_and_reaps_only_its_owned_child(monkeypatch, failure):
    owned = Mock(poll=Mock(return_value=None))
    unrelated = Mock()
    popen = Mock(return_value=owned)
    close = Mock()
    monkeypatch.setattr(terminal.pty, "openpty", lambda: (101, 102))
    monkeypatch.setattr(terminal.os, "close", close)
    monkeypatch.setattr(terminal.subprocess, "Popen", popen)
    monkeypatch.setattr(terminal.time, "monotonic", lambda: 0)
    monkeypatch.setattr(terminal.select, "select", lambda *args: ([101], [], []))
    monkeypatch.setattr(terminal.os, "read", lambda *args: b"")
    if failure == "spawn":
        popen.side_effect = OSError("spawn refused")
    elif failure == "timeout":
        monkeypatch.setattr(terminal.select, "select", lambda *args: ([], [], []))
    elif failure == "read":
        monkeypatch.setattr(terminal.os, "read", Mock(side_effect=OSError("read refused")))
    elif failure == "interrupt":
        monkeypatch.setattr(terminal.os, "read", Mock(side_effect=KeyboardInterrupt()))
    else:
        owned.wait.side_effect = [subprocess.TimeoutExpired("fixture", 1), 0]
    with pytest.raises((OSError, subprocess.TimeoutExpired, KeyboardInterrupt)):
        terminal.capture(["fixture"], {}, "xterm", timeout=1)
    assert owned.kill.call_count == (failure != "spawn")
    assert unrelated.mock_calls == []
    assert sorted(call.args[0] for call in close.call_args_list) == [101, 102]
