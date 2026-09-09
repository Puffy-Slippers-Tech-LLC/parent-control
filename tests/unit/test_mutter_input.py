"""Public input operations share a completed virtual-device session boundary."""

from unittest.mock import Mock, call

import pytest
from tests.ui import mutter_input


def test_pointer_and_keyboard_finish_delivery_before_the_next_action(monkeypatch):
    monkeypatch.setattr(mutter_input.time, 'sleep', Mock())
    backend = Mock()
    mutter_input.click_at(backend, 3, 40, 20)
    mutter_input.press_key(backend, 65)
    assert backend.mock_calls == [
        call.generateMotionEvent(40, 20), call.generateButtonPress(3),
        call.generateButtonRelease(3), call.disconnect(), call.connectMonitor(),
        call.generateKeycodePress(65), call.generateKeycodeRelease(65),
        call.disconnect(), call.connectMonitor(),
    ]


def test_failed_disconnect_does_not_start_another_input_session(monkeypatch):
    monkeypatch.setattr(mutter_input.time, 'sleep', Mock())
    backend = Mock(disconnect=Mock(side_effect=RuntimeError('input refused')))
    with pytest.raises(RuntimeError, match='input refused'):
        mutter_input.click_at(backend, 3, 40, 20)
    backend.connectMonitor.assert_not_called()
