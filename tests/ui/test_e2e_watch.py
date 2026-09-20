"""GTK spectator lifecycle, without touching the user's desktop or input."""

import json
import os
from pathlib import Path
import time

import pytest

pytestmark = pytest.mark.ui


def evidence(path):
    try:
        value = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def advance(path, stage):
    path.write_text(str(stage))


def run_probe(launch_ui, tmp_path, ui, wait, *, live=False, cycle=False):
    output = tmp_path / 'watch.json'
    control = tmp_path / 'watch-control'
    process, log_path = launch_ui('e2e_watch_window_probe', wait_for_application=False,
        environment_overrides={'ONPC_WATCH_EVIDENCE': str(output),
                               'ONPC_WATCH_CONTROL': str(control),
                               'ONPC_WATCH_LIVE': 'cycle' if cycle else str(int(live))})
    wait(lambda: ui.showing('e2e-watch-window'),
         'spectator publishes its owned window ID')
    assert ui.text('e2e-watch-status') == (
        'Waiting for an E2E VM. You can leave this window open.')
    for identity in ('e2e-watch-progress', 'e2e-watch-display',
                     'e2e-watch-output', 'e2e-watch-close'):
        assert ui.target(identity).get_accessible_id() == identity

    if live:
        key = 'closed_during_live_attempt' if cycle else 'stopped_window_still_open'
        wait(lambda: evidence(output).get(key), 'live spectator reaches its close point')
        assert ui.showing('e2e-watch-window')
    else:
        advance(control, 1)
        wait(lambda: ui.text('e2e-watch-progress') ==
             'For both variants, reject the wrong-account prompt. ' * 40,
             'spectator exposes the current customer step')
        assert ui.text('e2e-watch-status') == (
            'Selecting [Existing child] from the child selector ' * 20)
        wait(lambda: evidence(output).get('frame_format_and_progress_layout'),
             'synthetic frame rendering completes')

        advance(control, 2)
        wait(lambda: ui.text('e2e-watch-status').startswith(
             'Preparing VM: check-system: [stage:isolated] - ('),
             'preparation remains visible after display loss')
        wait(lambda: 'REBOOT REQUIRED' in ui.content('e2e-watch-output', maximum=8000),
             'bounded read-only command output is public')
        terminal = ui.content('e2e-watch-output', maximum=8000)
        assert 'SSH $ apt-get install' in terminal and 'PASS' in terminal
        assert '\x1b[' not in terminal
        assert ui.showing('e2e-watch-window')

        advance(control, 3)
        wait(lambda: ui.text('e2e-watch-progress') == 'First step after preparation',
             'the same spectator exposes resumed progress')
        wait(lambda: ui.text('e2e-watch-status') == 'Opening About - (1s)',
             'operation timing advances without another frame')
        wait(lambda: evidence(output).get('resize_did_not_change_guest'),
             'viewer resize remains isolated from the synthetic guest')

    ui.activate('e2e-watch-close')
    deadline = time.monotonic() + 10
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(.05)
    assert process.poll() == 0, log_path.read_text()
    return evidence(output), output


def test_window_survives_stop_reconnect_and_resize(
        launch_ui, tmp_path, automation, wait_for_accessible_state):
    result, output = run_probe(
        launch_ui, tmp_path, automation, wait_for_accessible_state)
    for name in ('frame_format_and_progress_layout',
                 'terminal_is_read_only_and_colored',
                 'resumed_frame_in_same_viewer', 'resize_did_not_change_guest'):
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
def test_live_window_can_close_during_automation(
        launch_ui, tmp_path, automation, wait_for_accessible_state):
    active_attempt()
    result, _ = run_probe(launch_ui, tmp_path, automation,
                          wait_for_accessible_state, live=True, cycle=True)
    assert result['closed_during_live_attempt']
    active_attempt()


@pytest.mark.live_e2e
def test_live_attempt_keeps_window_open_after_shutdown(
        launch_ui, tmp_path, automation, wait_for_accessible_state):
    active_attempt()
    result, _ = run_probe(launch_ui, tmp_path, automation,
                          wait_for_accessible_state, live=True)
    assert result['frames'] > 20 and result['reconnects'] == 6
    assert result['stopped_window_still_open']
