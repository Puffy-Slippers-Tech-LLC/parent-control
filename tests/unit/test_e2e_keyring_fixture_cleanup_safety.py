"""The keyring fixture signals only its directly spawned challenge child."""

from unittest.mock import Mock

import keyring_prompt_fixture as fixture


def test_failed_child_is_reaped_without_signalling():
    child = Mock()
    child.poll.return_value = 1
    fixture.stop_child(child)
    child.terminate.assert_not_called()
    child.kill.assert_not_called()
    child.wait.assert_called_once_with(timeout=5)


def test_live_child_is_terminated_and_reaped():
    child = Mock()
    child.poll.return_value = None
    fixture.stop_child(child)
    child.terminate.assert_called_once_with()
    child.kill.assert_not_called()
    child.wait.assert_called_once_with(timeout=5)


def test_unresponsive_owned_child_is_killed_and_reaped():
    child = Mock()
    child.poll.return_value = None
    child.wait.side_effect = [fixture.subprocess.TimeoutExpired('challenge', 5), 0]
    fixture.stop_child(child)
    child.terminate.assert_called_once_with()
    child.kill.assert_called_once_with()
    assert child.wait.call_count == 2
