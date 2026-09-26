"""Exercise fixture process ownership without discovering unrelated processes."""

import os
import signal
import subprocess
from unittest import mock

import pytest

from tests.fixtures.build_test_applications import FixtureError, launch_native, terminate


def test_native_gui_owner_keeps_its_executable_identity_and_reaps_its_child(tmp_path):
    from tests.fixtures import build_test_applications as fixtures
    import select
    from pathlib import Path

    binary = fixtures._compile_native(tmp_path)
    (binary.parent / 'onpc-test-gui.py').write_text(
        'import signal\n'
        # Block before publishing readiness, then consume the pending signal
        # atomically. Python defers handlers: SIGTERM between entering pause()
        # and its syscall can otherwise leave a pending handler asleep forever.
        'signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})\n'
        'print("GUI_READY", flush=True)\n'
        'assert signal.sigwait({signal.SIGTERM}) == signal.SIGTERM\n'
        'print("GUI_STOPPED", flush=True)\n', encoding='utf-8')
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


@pytest.mark.parametrize(('script', 'expected'), [
    ('raise SystemExit(23)\n', 23),
    ('import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n', 128 + signal.SIGTERM),
])
def test_native_gui_owner_propagates_child_failure_status(tmp_path, script, expected):
    from tests.fixtures import build_test_applications as fixtures

    binary = fixtures._compile_native(tmp_path)
    (binary.parent / 'onpc-test-gui.py').write_text(script, encoding='utf-8')
    completed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert completed.returncode == expected


def test_native_gui_owner_reports_missing_gui_without_leaving_a_child(tmp_path):
    from tests.fixtures import build_test_applications as fixtures

    binary = fixtures._compile_native(tmp_path)
    (binary.parent / 'onpc-test-gui.py').unlink()
    completed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert completed.returncode != 0
    assert 'onpc-test-gui.py' in completed.stderr


def test_mechanical_fixture_remains_one_shot_and_has_no_gui_payload(tmp_path):
    from tests.fixtures import build_test_applications as fixtures

    binary = fixtures._compile_native(tmp_path, headless=True)
    completed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert completed.returncode == 0
    assert completed.stdout == 'ONPC_TEST_APPLICATION_READY\n'
    assert not (binary.parent / 'onpc-test-gui.py').exists()


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


def test_failed_native_readiness_reaps_only_the_spawned_process(tmp_path):
    binary = tmp_path / 'fixture'
    binary.write_bytes(b'fixture')
    binary.chmod(0o755)
    process = mock.Mock(stdout=mock.Mock(), stderr=mock.Mock())
    process.poll.return_value = None
    with mock.patch('tests.fixtures.build_test_applications.subprocess.Popen', return_value=process), \
            mock.patch('tests.fixtures.build_test_applications._read_readiness', return_value='WRONG'):
        with pytest.raises(FixtureError, match='did not report readiness'):
            launch_native(binary, os.geteuid())
    process.send_signal.assert_called_once_with(signal.SIGTERM)
    process.wait.assert_called_once_with(timeout=5)
    process.stdout.close.assert_called_once_with()
    process.stderr.close.assert_called_once_with()
