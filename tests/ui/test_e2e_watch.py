"""GTK spectator lifecycle, without touching the user's desktop or input."""

import json
import os
from pathlib import Path
import time

import pytest

pytestmark = pytest.mark.ui


def run_probe(launch_ui, tmp_path, *, live=False, cycle=False):
    output = tmp_path / 'watch.json'
    process, log_path = launch_ui('e2e_watch_window_probe', wait_for_application=False,
        environment_overrides={'ONPC_WATCH_EVIDENCE': str(output),
                               'ONPC_WATCH_LIVE': 'cycle' if cycle else str(int(live))})
    deadline = time.monotonic() + (1250 if live else 20)
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(.1)
    assert process.poll() == 0, log_path.read_text()
    assert output.exists(), log_path.read_text()
    return json.loads(output.read_text()), output


def test_window_survives_stop_reconnect_and_resize(launch_ui, tmp_path):
    result, output = run_probe(launch_ui, tmp_path)
    for name in ('waiting_window_open', 'stopped_window_still_open',
                 'resumed_same_window', 'resize_did_not_change_guest',
                 'progress_visible_and_truncated', 'preparation_visible_without_vm',
                 'ssh_visible_without_vm', 'terminal_colors_rendered'):
        assert result[name]
    from PIL import Image
    image = Image.open(output.with_suffix('.png')).convert('RGB')
    assert image.size == (4, 3)
    assert image.getpixel((0, 0)) == (255, 0, 0)


def active_attempt():
    # Explicit live acceptance selection runs alongside a real E2E attempt.
    # Ordinary UI suites do not require or start a VM.
    if not (Path('/run/onpc-e2e-watch') / str(os.getuid()) / 'current.json').exists():
        pytest.skip('Select during an active E2E attempt for live acceptance')


@pytest.mark.live_e2e
def test_live_window_can_close_during_automation(launch_ui, tmp_path):
    active_attempt()
    result, _ = run_probe(launch_ui, tmp_path, live=True, cycle=True)
    assert result['closed_during_live_attempt']
    active_attempt()


@pytest.mark.live_e2e
def test_live_attempt_keeps_window_open_after_shutdown(launch_ui, tmp_path):
    active_attempt()
    result, _ = run_probe(launch_ui, tmp_path, live=True)
    assert result['frames'] > 20 and result['reconnects'] == 6
    assert result['stopped_window_still_open']
