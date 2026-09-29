"""Combined viewer behavior on a private compositor, with no live VM."""

import json

import pytest

from tests.support.automation_ids import audit_owned_controls

pytestmark = pytest.mark.ui


def test_combined_tabs_output_dividers_and_hidden_viewers(
        launch_ui, tmp_path, automation, wait_for_accessible_state):
    ui, wait = automation, wait_for_accessible_state
    process, log = launch_ui('watch_window_probe', wait_for_application=False,
                            environment_overrides={'ONPC_WATCH_FIXTURE': str(tmp_path)})
    control = tmp_path / 'control'
    def evidence():
        try:
            return json.loads((tmp_path / 'evidence.json').read_text())
        except (OSError, ValueError):
            return {}
    wait(lambda: ui.showing('watch-window'), 'combined watcher opens')
    assert ui.showing('watch-waiting')
    control.write_text('ui')
    wait(lambda: ui.text('watch-tab-active') == 'Active - UI', 'UI activity changes Active tab')
    wait(lambda: 'RUN OUTPUT' in ui.content('watch-output', maximum=10000), 'runner output is visible')
    wait(lambda: 'END WRAPPED' in ui.content('watch-output', maximum=10000), 'long terminal line wraps')
    wait(lambda: 'RUN PROGRESS' in ui.content('watch-output', maximum=10000), 'live runner dashboard appears')
    run = evidence()['run']
    assert ui.text(f'ui-watch-grid-{run}-test') == 'UI first'
    control.write_text('both')
    wait(lambda: ui.text('watch-tab-active') == 'Active - UI + VM', 'both viewers share Active')
    wait(lambda: ui.text('e2e-watch-progress') == 'VM first', 'VM progress is visible beside UI')
    assert ui.showing(f'ui-watch-grid-{run}-display') and ui.showing('e2e-watch-display')
    audit_owned_controls(ui, 'watch-window')
    control.write_text('split-check')
    wait(lambda: evidence().get('dividers_resized'), 'both native dividers resize independently')
    layout = evidence()
    assert .27 < layout['columns_ratio'] < .33
    assert .47 < layout['rows_ratio'] < .53
    assert layout['icon'] == 'org.onpc.E2EWatch'
    assert (layout['no_horizontal_scroll'] and layout['terminal_readonly']
            and layout['terminal_colored'] and layout['terminal_selectable'])
    assert layout['terminal_columns'] < 60

    ui.activate('watch-tab-ui')
    wait(lambda: ui.showing('watch-page-ui'), 'UI-only tab opens')
    assert ui.showing(f'ui-watch-grid-{run}-test')
    control.write_text('hide-vm')
    wait(lambda: evidence().get('vm_frozen'), 'hidden VM stops rendering despite new publications')
    wait(lambda: 'FIX OUTPUT' in ui.content('watch-output', maximum=10000), 'fix-tests takes output priority')
    assert ui.text('watch-output-status') == 'Terminal Outputs — fix-tests'
    ui.activate('watch-tab-vm')
    wait(lambda: ui.showing('watch-page-vm'), 'VM-only tab opens')
    wait(lambda: ui.text('e2e-watch-progress') == 'VM next', 'reactivated VM shows current state')
    control.write_text('hide-ui')
    wait(lambda: evidence().get('ui_frozen'), 'hidden UI stops updating despite new publications')
    ui.activate('watch-tab-active')
    wait(lambda: ui.showing(f'ui-watch-grid-{run}-test'), 'Active restores its UI panel')
    wait(lambda: ui.text(f'ui-watch-grid-{run}-test') == 'UI next', 'Active restores current UI state')
    control.write_text('vm-only')
    wait(lambda: ui.text('watch-tab-active') == 'Active- VM', 'finished UI leaves VM at full height')
    wait(lambda: ui.text('watch-output-status') == 'Terminal Outputs — run-tests', 'runner resumes after repair')
    control.write_text('idle')
    wait(lambda: ui.showing('watch-waiting'), 'both completed feeds leave watcher open')
    wait(lambda: ui.text('watch-output-status') == 'Terminal Outputs — run-tests (finished)',
         'completed terminal transcript remains available')
    ui.activate('watch-close')
    wait(lambda: process.poll() is not None, 'closing viewer releases only its own resources')
    assert process.returncode == 0, log.read_text()
