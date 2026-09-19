"""Public input operations share a completed virtual-device session boundary."""

from unittest.mock import Mock, call

import pytest
from tests.ui import mutter_input


def test_keyboard_finishes_delivery_before_the_next_action(monkeypatch):
    monkeypatch.setattr(mutter_input.time, 'sleep', Mock())
    backend = Mock()
    mutter_input.press_key(backend, 65)
    assert backend.mock_calls == [
        call.generateKeycodePress(65), call.generateKeycodeRelease(65),
        call.disconnect(), call.connectMonitor(),
    ]


def test_failed_disconnect_does_not_start_another_input_session(monkeypatch):
    monkeypatch.setattr(mutter_input.time, 'sleep', Mock())
    backend = Mock(disconnect=Mock(side_effect=RuntimeError('input refused')))
    with pytest.raises(RuntimeError, match='input refused'):
        mutter_input.press_key(backend, 65)
    backend.connectMonitor.assert_not_called()


def test_retained_coordinate_entry_point_refuses_before_any_input():
    backend = Mock()
    with pytest.raises(RuntimeError, match='ID-addressed semantic action'):
        mutter_input.click_at(backend, 3, 40, 20)
    assert backend.mock_calls == []
