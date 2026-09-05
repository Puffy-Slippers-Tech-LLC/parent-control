"""Exercise fixture process ownership without starting or signalling processes."""

import signal
import subprocess
from unittest import mock

import pytest

from tests.fixtures.build_test_applications import FixtureError, terminate


@pytest.mark.parametrize("exited", [False, True])
def test_cleanup_signals_only_the_supplied_process_handle(exited):
    process = mock.Mock()
    process.poll.return_value = 0 if exited else None
    with mock.patch("os.kill") as kill, mock.patch("os.killpg") as killpg:
        terminate(process)
    if exited:
        process.send_signal.assert_not_called()
    else:
        process.send_signal.assert_called_once_with(signal.SIGTERM)
    process.wait.assert_called_once_with(timeout=5)
    kill.assert_not_called()
    killpg.assert_not_called()


def test_timeout_does_not_expand_cleanup_to_other_processes():
    process = mock.Mock()
    process.poll.return_value = None
    process.wait.side_effect = subprocess.TimeoutExpired("fixture", 5)
    with mock.patch("os.kill") as kill, mock.patch("os.killpg") as killpg:
        with pytest.raises(FixtureError, match="did not terminate"):
            terminate(process)
    process.send_signal.assert_called_once_with(signal.SIGTERM)
    kill.assert_not_called()
    killpg.assert_not_called()
