"""View-only tabs, four-worker grid and attachment to the real test compositor."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from tests.support.automation_ids import audit_owned_controls
from tests.support.request_form import launch_request, calls, events as request_events
from ui_watch_transport import Feeds
from ui_watch_viewer import WAITING

pytestmark = pytest.mark.ui


@pytest.fixture
def watch_registry():
    with tempfile.TemporaryDirectory(prefix='onpc-ui-watch-test-', dir='/tmp') as directory:
        yield Path(directory)


def test_four_branch_tabs_grid_resize_stop_and_reconnect(
        launch_ui, automation, wait_for_accessible_state, tmp_path, watch_registry):
    directory = watch_registry
    control, evidence = tmp_path / 'control', tmp_path / 'evidence.json'
    process, log = launch_ui('ui_watch_window_probe', environment_overrides={
        'ONPC_UI_WATCH_REGISTRY': str(directory), 'ONPC_UI_WATCH_CONTROL': str(control),
        'ONPC_UI_WATCH_EVIDENCE': str(evidence)})
    ui, wait = automation, wait_for_accessible_state
    wait(lambda: ui.showing('ui-watch-window'), 'viewer publishes its window')
    assert ui.text('ui-watch-status') == WAITING
    control.write_text('start')
    wait(lambda: ui.text('ui-watch-status') == '4 active UI worker(s) · View only',
         'viewer independently discovers all four workers')
    runs = json.loads(evidence.read_text())['runs']
    for index, run in enumerate(runs):
        assert ui.text(f'ui-watch-grid-{run}-test') == f'case-{index + 1}'
        assert ui.showing(f'ui-watch-grid-{run}-display')
        ui.activate('ui-watch-tab-' + run)
        wait(lambda: ui.showing(f'ui-watch-branch-{run}-test'), 'selected branch is visible')
        assert ui.text(f'ui-watch-branch-{run}-test') == f'case-{index + 1}'
        ui.activate('ui-watch-all-tab')
        wait(lambda: all(ui.showing(f'ui-watch-grid-{worker}-test') for worker in runs),
             'All branches restores every worker view')
    audit_owned_controls(ui, 'ui-watch-window')
    control.write_text('resize')
    wait(lambda: all(ui.text(f'ui-watch-grid-{run}-status').startswith('teardown') for run in runs),
         'all workers keep publishing after viewer resize')
    control.write_text('stop')
    wait(lambda: ui.text('ui-watch-status') == WAITING, 'finished workers clear from viewer')
    control.write_text('resume')
    wait(lambda: ui.text('ui-watch-status') == '1 active UI worker(s) · View only',
         'same viewer discovers a subsequent worker')
    run = json.loads(evidence.read_text())['runs'][0]
    assert ui.text(f'ui-watch-grid-{run}-test') == 'subsequent-case'
    ui.activate('ui-watch-close')
    wait(lambda: process.poll() is not None, 'viewer exits independently')
    assert process.returncode == 0, log.read_text()


def test_live_capture_detach_reattach_preserves_public_actions(
        hermetic_ui_session, launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui, wait = automation, wait_for_accessible_state
    _process, events = launch_request(launch_ui, tmp_path, overlay=False, wait_for_application=False)
    wait(lambda: ui.showing('kiosk-request-submit'), 'test form publishes its control')
    wait(lambda: ui.state('kiosk-request-submit', ui.api.StateType.SENSITIVE), 'form is ready')
    feeds = Feeds()
    observed = {}

    def live():
        for run, frame in feeds.poll().items():
            if frame[1].get('worker') == os.getpid():
                observed['run'], observed['frame'] = run, frame
                assert frame[1]['state'] != 'unavailable', 'Capture failed; inspect UI watch diagnostics'
                return frame[1]['state'] == 'live'
        return False

    try:
        wait(live, 'private monitor capture publishes a real video sample')
        before = observed['frame'][0]
        assert 'test_live_capture_detach_reattach' in observed['frame'][1]['test']
        feeds.close()
        ui.activate('kiosk-approver-selector')
        wait(lambda: ui.showing('kiosk-approver-choice-1010'), 'declared approver is available')
        ui.activate('kiosk-approver-choice-1010')
        ui.activate('kiosk-duration-300')
        ui.activate('kiosk-request-submit')
        wait(lambda: bool(calls(events, 'RequestAccess')), 'request commits after viewer detaches')
        assert calls(events, 'RequestAccess')[0]['values'] == [1001, 1010, 300, False]
        feeds.next_scan = 0
        wait(live, 'reattachment observes the same continuing UI worker')
        assert observed['frame'][0] > before
        wait(lambda: ui.showing('kiosk-result-action'), 'approval result remains reachable')
        ui.activate('kiosk-result-action')
        wait(lambda: bool(request_events(events, 'logout')), 'result action works after reattachment')
    finally:
        feeds.close()


@pytest.mark.parametrize('dpi_scale', (1.25, 1, 1.25))
def test_live_capture_survives_display_scale_changes(
        hermetic_ui_session, launch_ui, automation, wait_for_accessible_state,
        temporary_display_scale, dpi_scale, tmp_path):
    """Real scale changes and fixture restoration must not kill the spectator."""
    ui, wait = automation, wait_for_accessible_state
    launch_request(launch_ui, tmp_path, overlay=False, wait_for_application=False)
    wait(lambda: ui.showing('kiosk-request-submit'), 'form publishes its control')
    feeds = Feeds()
    observed = {}

    def live_after(timestamp, generation=0):
        for run, frame in feeds.poll().items():
            meta = frame[1]
            if meta.get('worker') == os.getpid():
                assert meta['state'] != 'unavailable', meta.get('detail')
                if (meta['state'] == 'live' and meta.get('captured_ns', 0) > timestamp
                        and meta.get('capture_generation', 0) > generation):
                    observed['run'] = run
                    observed['generation'] = meta['capture_generation']
                    return True
        return False

    try:
        wait(lambda: live_after(0), 'initial video sample arrives')
        run = observed['run']
        # Use the same public configuration as Layout and overflow. Observe
        # the replacement stream, not a late sample from the outgoing stream,
        # and verify restoration here instead of leaking an outage to the next case.
        for _ in range(3):
            generation = observed['generation']
            with temporary_display_scale(dpi_scale):
                changed = time.monotonic_ns()
                ui.activate('kiosk-duration-300')
                wait(lambda: live_after(changed, generation),
                     'replacement capture delivers video after scaling')
                assert observed['run'] == run, 'recovery preserves the branch identity'
                assert ui.state('kiosk-duration-300', ui.api.StateType.PRESSED)
                generation = observed['generation']
                restored = time.monotonic_ns()
            wait(lambda: live_after(restored, generation),
                 'replacement capture delivers video after scale restoration')
            assert observed['run'] == run, 'restoration preserves the branch identity'
    finally:
        feeds.close()
