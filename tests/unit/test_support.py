"""Behavioral regressions for shared test support, without product services."""

import os
import json
import subprocess
import sys
from types import ModuleType

import pytest

from tests.support.configuration import valid_config
from tests.support.events import read_events
from tests.support.modules import load_module
from tests.support.terminal import capture


def test_configuration_factory_returns_independent_documents():
    first = valid_config()
    first["kiosk_uid"] = 1234
    assert valid_config()["kiosk_uid"] == 991


def test_event_reader_waits_for_complete_records_and_accepts_missing_files(tmp_path):
    path = tmp_path / "events.jsonl"
    assert read_events(path) == []
    path.write_text('{"event": "ready"}\n{"event": "sav')
    assert read_events(path) == [{"event": "ready"}]
    with path.open("a") as stream:
        stream.write('ed"}\n')
    assert read_events(path) == [{"event": "ready"}, {"event": "saved"}]


def test_event_reader_does_not_hide_corrupt_completed_records(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('not-json\n')
    with pytest.raises(json.JSONDecodeError):
        read_events(path)


def test_script_loader_supports_dataclasses_and_fresh_state(tmp_path, monkeypatch):
    name = "onpc_test_loader_fixture"
    monkeypatch.setitem(sys.modules, name, ModuleType(name))
    source = tmp_path / "module.py"
    source.write_text("from dataclasses import dataclass\n"
                      "@dataclass\nclass Value:\n    count: int = 1\nstate = []\n")
    first = load_module(name, source)
    first.state.append("mutated")
    second = load_module(name, source)
    assert first is not second and second.state == []
    assert second.Value().count == 1
    assert sys.modules[name] is second


@pytest.mark.parametrize("previous", [False, True])
@pytest.mark.parametrize("failure", ["RuntimeError", "KeyboardInterrupt"])
def test_failed_script_load_restores_the_import_registry(tmp_path, monkeypatch, previous, failure):
    name = "onpc_test_loader_failure"
    original = ModuleType(name)
    if previous:
        monkeypatch.setitem(sys.modules, name, original)
    else:
        monkeypatch.delitem(sys.modules, name, raising=False)
    source = tmp_path / "module.py"
    source.write_text(f"raise {failure}('fixture failure')\n")
    with pytest.raises((RuntimeError, KeyboardInterrupt)):
        load_module(name, source)
    assert sys.modules.get(name) is (original if previous else None)


@pytest.mark.parametrize("terminal", [None, "xterm", "dumb"])
def test_terminal_capture_drains_more_than_a_pty_buffer_and_retains_exit_status(terminal):
    command = [sys.executable, "-c", "import sys; print('x' * 200000); sys.exit(7)"]
    result, output = capture(command, os.environ, terminal)
    assert result.returncode == 7
    assert output.rstrip() == "x" * 200000


def test_terminal_capture_has_a_real_deadline():
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(subprocess.TimeoutExpired):
        capture(command, os.environ, "xterm", timeout=0.1)
