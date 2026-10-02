"""Behavioral regressions for shared test support, without product services."""

import os
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from tests.support.configuration import valid_config
from tests.support.events import read_events
from tests.support.modules import load_module
from tests.support.terminal import capture
from tests.support.preview import boot_preview_session


@pytest.mark.parametrize('fault', ['', 'recipient', 'partial', 'uncertain'])
def test_bounded_cursor_movement_preserves_recipient_and_single_use(monkeypatch, fault):
    # In-memory doubles; no new paths, processes, displays or scheduling resource.
    from unittest.mock import Mock
    from tests.support import keyboard
    key = Mock(side_effect=[None, RuntimeError('partial')] if fault == 'partial' else None)
    dogtail = ModuleType('dogtail')
    dogtail.rawinput = SimpleNamespace(keyCombo=key)
    monkeypatch.setitem(sys.modules, 'dogtail', dogtail)
    configuration = ModuleType('dogtail.config')
    configuration.config = SimpleNamespace(action_delay=1)
    monkeypatch.setitem(sys.modules, 'dogtail.config', configuration)
    node = Mock()
    node.get_state_set.return_value.contains.return_value = fault != 'recipient'
    ui = SimpleNamespace(input_uncertain=fault == 'uncertain', id_target=Mock(return_value=node),
                         api=SimpleNamespace(StateType=SimpleNamespace(FOCUSED='focused')))
    if fault:
        with pytest.raises((AssertionError, RuntimeError)):
            keyboard.repeat_cursor(ui, 'owned-editor', '<Shift>Right', 3)
        assert key.call_count == (2 if fault == 'partial' else 0)
        if fault == 'partial':
            assert ui.input_uncertain
            with pytest.raises(AssertionError, match='uncertain'):
                keyboard.repeat_cursor(ui, 'owned-editor', '<Shift>Right', 3)
            assert key.call_count == 2
    else:
        keyboard.repeat_cursor(ui, 'owned-editor', '<Shift>Right', 3)
        assert [call.args for call in key.call_args_list] == [('<Shift>Right',)] * 3
        ui.id_target.assert_called_once_with('owned-editor')
        assert not ui.input_uncertain
    assert configuration.config.action_delay == 1


@pytest.mark.parametrize('keys,count', [('Return', 2), ('Right', -1), ('Right', 129),
                                       ('Right', True), ('Right', 1.5)])
def test_cursor_batches_refuse_unbounded_or_transition_input(keys, count):
    from tests.support.keyboard import repeat_cursor
    with pytest.raises(ValueError, match='bounded cursor'):
        repeat_cursor(None, 'owned-editor', keys, count)


@pytest.mark.parametrize('fault', ['', 'recipient', 'partial', 'uncertain', 'cancelled'])
@pytest.mark.parametrize('post_delay', [None, 0.05])
def test_keyboard_chord_pacing_restores_defaults_and_preserves_single_use(
        monkeypatch, fault, post_delay):
    # Process-local input/config doubles; no real keyboard, display or sleep.
    from unittest.mock import Mock
    from tests.support import keyboard
    configuration = ModuleType('dogtail.config')
    configuration.config = SimpleNamespace(action_delay=1)
    monkeypatch.setitem(sys.modules, 'dogtail.config', configuration)
    deliveries = []
    def send(keys):
        deliveries.append((keys, configuration.config.action_delay))
        if fault == 'partial':
            raise RuntimeError('partial delivery')
        if fault == 'cancelled':
            raise KeyboardInterrupt()
    dogtail = ModuleType('dogtail')
    dogtail.rawinput = SimpleNamespace(keyCombo=send)
    monkeypatch.setitem(sys.modules, 'dogtail', dogtail)
    node = Mock()
    node.get_state_set.return_value.contains.return_value = fault != 'recipient'
    ui = SimpleNamespace(input_uncertain=fault == 'uncertain', id_target=Mock(return_value=node))
    def deliver():
        keyboard.key_combo(ui, 'owned-popup', 'Escape', state='active', post_delay=post_delay)
    if fault:
        with pytest.raises((AssertionError, RuntimeError, KeyboardInterrupt)):
            deliver()
    else:
        deliver()
        assert not ui.input_uncertain
    expected = [('Escape', 1 if post_delay is None else post_delay)]
    assert deliveries == ([] if fault in ('recipient', 'uncertain') else expected)
    assert configuration.config.action_delay == 1
    if fault in ('partial', 'cancelled'):
        assert ui.input_uncertain
        with pytest.raises(AssertionError, match='uncertain'):
            deliver()
        assert deliveries == expected
    if fault != 'uncertain':
        ui.id_target.assert_called_once_with('owned-popup')


@pytest.mark.parametrize('delay', [-1, 1, float('nan'), True, '0.05'])
def test_keyboard_chord_refuses_invalid_post_delay_before_input(delay):
    from tests.support import keyboard
    with pytest.raises(ValueError, match='post-action delay'):
        keyboard.key_combo(None, 'owned-popup', 'Escape', state='active', post_delay=delay)


@pytest.mark.parametrize('failure', [False, True])
def test_paced_keyboard_input_is_single_use_and_latches_partial_delivery(monkeypatch, failure):
    # Process-local doubles only; no real input, delay, display or added resource.
    from unittest.mock import Mock
    from tests.support import keyboard
    events = []
    def press(character):
        events.append(('key', character))
        if failure and character == 'b':
            raise RuntimeError('partial delivery')
    dogtail = ModuleType('dogtail')
    dogtail.rawinput = SimpleNamespace(pressKey=press, typeText=Mock())
    monkeypatch.setitem(sys.modules, 'dogtail', dogtail)
    monkeypatch.setattr(keyboard.time, 'sleep', lambda delay: events.append(('wait', delay)))
    node = Mock()
    ui = SimpleNamespace(input_uncertain=False, id_target=Mock(return_value=node),
                         api=SimpleNamespace(StateType=SimpleNamespace(FOCUSED='focused')))
    if failure:
        with pytest.raises(RuntimeError, match='partial delivery'):
            keyboard.type_text(ui, 'owned-field', 'abc', interval=0.02)
        assert ui.input_uncertain
        with pytest.raises(AssertionError, match='uncertain'):
            keyboard.type_text(ui, 'owned-field', 'abc', interval=0.02)
        assert events == [('key', 'a'), ('wait', 0.02), ('key', 'b')]
    else:
        keyboard.type_text(ui, 'owned-field', 'abc', interval=0.02)
        assert not ui.input_uncertain
        assert events == [(kind, value) for c in 'abc'
                          for kind, value in (('key', c), ('wait', 0.02))]
    dogtail.rawinput.typeText.assert_not_called()
    ui.id_target.assert_called_once_with('owned-field')


@pytest.mark.parametrize('interval', [-1, 1, float('nan'), True, '0.02'])
def test_keyboard_pacing_rejects_invalid_intervals_before_input(interval):
    from tests.support import keyboard
    with pytest.raises(ValueError, match='interval'):
        keyboard.type_text(None, 'owned-field', 'abc', interval=interval)


@pytest.mark.parametrize('previous', [None, '/var/tmp'])
@pytest.mark.parametrize('failure', [None, RuntimeError, KeyboardInterrupt])
def test_graphical_boot_restores_pytest_storage_default(monkeypatch, previous, failure):
    monkeypatch.setattr(tempfile, 'tempdir', previous)
    monkeypatch.setenv('TMPDIR', '/var/tmp')

    def boot():
        with tempfile.TemporaryDirectory(prefix='onpc-runtime-probe-') as directory:
            assert Path(directory).parent == Path('/tmp')
            if failure:
                raise failure('boot failed')

    session = SimpleNamespace(boot=boot)
    if failure:
        with pytest.raises(failure):
            boot_preview_session(session)
    else:
        boot_preview_session(session)
    assert tempfile.tempdir == previous
    assert os.environ['TMPDIR'] == '/var/tmp'


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
