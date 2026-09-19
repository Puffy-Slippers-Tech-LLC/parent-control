"""Exercise fixture process ownership without starting or signalling processes."""

import signal
import subprocess
from unittest import mock

import pytest

from tests.fixtures.build_test_applications import FixtureError, terminate


def test_native_gui_owner_keeps_its_executable_identity_and_reaps_its_child(tmp_path):
    from tests.fixtures import build_test_applications as fixtures
    import select
    from pathlib import Path

    binary = fixtures._compile_native(tmp_path)
    (binary.parent / 'onpc-test-gui.py').write_text(
        'import signal, sys\n'
        'def stop(*_):\n    print("GUI_STOPPED", flush=True)\n    sys.exit(0)\n'
        'signal.signal(signal.SIGTERM, stop)\n'
        'print("GUI_READY", flush=True)\n'
        'signal.pause()\n', encoding='utf-8')
    process = subprocess.Popen([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([process.stdout], [], [], 5)[0]
        assert process.stdout.readline().strip() == 'GUI_READY'
        assert Path(f'/proc/{process.pid}/exe').resolve() == binary
        process.terminate()
        process.wait(timeout=5)
        assert process.stdout.read().strip() == 'GUI_STOPPED'
    finally:
        terminate(process)


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
