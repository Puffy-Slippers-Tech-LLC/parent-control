"""Combined viewer behavior on a private compositor, with no live VM."""
from tests.support.vm_registry import vm_name

import json

import pytest

from tests.support.automation_ids import audit_owned_controls

pytestmark = pytest.mark.ui


def test_checkout_tabs_grid_idle_fallback_and_session_singleton(
        launch_ui, tmp_path, automation, wait_for_accessible_state):
    ui, wait = automation, wait_for_accessible_state
    process, log = launch_ui('watch_window_probe', wait_for_application=False,
        environment_overrides={'ONPC_WATCH_FIXTURE': str(tmp_path), 'ONPC_WATCH_CHECKOUTS': '1'})
    control = tmp_path / 'control'

    def evidence():
        try:
            return json.loads((tmp_path / 'evidence.json').read_text())
        except (OSError, ValueError):
            return {}

    wait(lambda: ui.showing('watch-window') and bool(evidence().get('keys')), 'checkout viewer opens')
    keys = evidence()['keys']
    for name, key in keys.items():
        assert ui.text('watch-checkout-tab-' + key) == name
    assert ui.showing('watch-checkout-tab-all')
    for count in (1, 2, 3):
        control.write_text('count-' + str(count))
        names = ['main', 'worktree', 'third'][:count]
        expected = {name: [0, index, 1, 1] for index, name in enumerate(names)}
        wait(lambda: evidence().get('cells') == expected and evidence().get('active') == names,
             'active terminals split into equal vertical sections in bottom-tab order')
        titles = []
        for name in names:
            titles.append(f'[{name}]: UI - Category A')
            if name == 'main':
                titles.append(f'[{name}]: UI - Category B')
            titles.append(f'[{name}]: Fixture-VM')
        viewer_expected = {title: [index % 2, index // 2, 1, 1]
                           for index, title in enumerate(titles)}
        wait(lambda: evidence().get('viewer_cells') == viewer_expected,
             'one flat grid orders each branch UI categories before its VM')
        top_titles = []
        for name in ('main', 'worktree', 'third'):
            if name in names:
                top_titles.append(f'[{name}]: UI - Category A')
                if name == 'main':
                    top_titles.append(f'[{name}]: UI - Category B')
            top_titles.append(f'[{name}]: Fixture-VM')
        assert evidence()['top_tabs'] == ['All', *top_titles]
        assert evidence()['blank'] == (len(titles) % 2 == 1)
        wait(lambda: len(evidence().get('terminal_heights', [])) == count and
             max(evidence()['terminal_heights']) - min(evidence()['terminal_heights']) <= 1,
             'terminal sections receive equal height')
        for name in names:
            prefix = 'watch-checkout-' + keys[name] + '-'
            wait(lambda: name + ' OUTPUT' in ui.content(prefix + 'watch-output', maximum=10000),
                 'each checkout shows its own runner transcript')
            assert ui.text('watch-checkout-heading-' + keys[name]) == name
    audit_owned_controls(ui, 'watch-window')
    control.write_text('remote')
    wait(lambda: evidence().get('remote_exited') and evidence().get('remote_received'),
         'another checkout forwards to the same desktop-session singleton')
    assert process.poll() is None and evidence()['cells'] == expected
    control.write_text('double-click-ui')
    wait(lambda: evidence().get('selected_viewer', 'all') != 'all',
         'double click opens the corresponding flat top tab without switching branch scope')
    assert evidence()['selected'] == 'all'
    assert evidence()['selected_viewer'] == keys['worktree'] + '-' + evidence()['ui_keys']['worktree']
    ui.activate('watch-all-watch-tab-all')
    wait(lambda: evidence().get('viewer_cells') == viewer_expected, 'All restores the flat viewer grid')
    ui.activate('watch-checkout-heading-' + keys['third'])
    wait(lambda: evidence().get('selected') == 'third', 'one click opens the active terminal branch')
    ui.activate('watch-checkout-tab-all')
    wait(lambda: evidence().get('viewer_cells') == viewer_expected, 'bottom All restores every viewer')
    control.write_text('finish-terminals')
    wait(lambda: evidence().get('output_active') == [] and len(evidence().get('cells', {})) == 1,
         'finishing terminals shrink the left panel while UI and VM viewers stay active')
    assert evidence()['viewer_cells'] == viewer_expected
    assert evidence()['active'] == names
    ui.activate('watch-checkout-tab-' + keys['third'])
    wait(lambda: evidence().get('selected') == 'third', 'finished branch remains selectable')
    assert ui.showing('watch-checkout-page-' + keys['third'])
    wait(lambda: evidence().get('top_tabs') == ['All', 'UI - Category A', 'Fixture-VM'],
         'individual branch tabs have one unprefixed viewer tab row')
    prefix = 'watch-checkout-' + keys['third'] + '-'
    assert 'third OUTPUT' in ui.content(prefix + 'watch-output', maximum=10000)
    ui.activate('watch-checkout-tab-all')
    wait(lambda: evidence().get('viewer_cells') == viewer_expected, 'All restores the flat viewer grid')
    control.write_text('count-1')
    wait(lambda: evidence().get('cells') == {'main': [0, 0, 1, 1]}, 'one active checkout fills All')
    main_viewers = {title: [index % 2, index // 2, 1, 1]
                    for index, title in enumerate(titles[:3])}
    wait(lambda: evidence().get('viewer_cells') == main_viewers and evidence().get('blank'),
         'one branch still has three flat viewer cells and an empty final right cell')
    control.write_text('count-0')
    wait(lambda: evidence().get('active') == [] and evidence().get('cells') == {'main': [0, 0, 1, 1]},
         'last finished checkout remains visible when all are idle')
    wait(lambda: evidence().get('viewer_cells') == {} and not evidence().get('blank'),
         'idle viewer grid clears independently of the retained terminal')
    assert 'main OUTPUT' in ui.content('watch-checkout-' + keys['main'] + '-watch-output', maximum=10000)
    # A different checkout finishing last replaces the idle fallback.
    control.write_text('count-3')
    wait(lambda: len(evidence().get('active', [])) == 3, 'finished checkouts reconnect')
    control.write_text('count-1')
    wait(lambda: evidence().get('active') == ['main'], 'other checkout activity ends')
    control.write_text('count-3')
    wait(lambda: len(evidence().get('active', [])) == 3, 'third checkout restarts')
    control.write_text('finish-main')
    wait(lambda: 'main' not in evidence().get('active', ['main']), 'main becomes inactive')
    control.write_text('count-0')
    wait(lambda: evidence().get('active') == [] and len(evidence().get('cells', {})) == 1,
         'last finishing checkout fills the idle grid')
    assert 'main' not in evidence()['cells']
    ui.activate('watch-checkout-tab-' + keys['worktree'])
    wait(lambda: ui.showing('watch-checkout-page-' + keys['worktree']), 'finished tab remains selectable')
    assert 'worktree OUTPUT' in ui.content('watch-checkout-' + keys['worktree'] + '-watch-output', maximum=10000)
    ui.activate('watch-close')
    wait(lambda: process.poll() is not None, 'viewer closes without controlling tests')
    assert process.returncode == 0, log.read_text()


@pytest.mark.parametrize('vm_name', [vm_name(), vm_name(1)])
def test_combined_tabs_output_dividers_and_hidden_viewers(
        launch_ui, tmp_path, automation, wait_for_accessible_state, vm_name):
    ui, wait = automation, wait_for_accessible_state
    process, log = launch_ui('watch_window_probe', wait_for_application=False,
                            environment_overrides={'ONPC_WATCH_FIXTURE': str(tmp_path),
                                                   'ONPC_TEST_VM': vm_name})
    control = tmp_path / 'control'
    vm_key = 'vm-' + vm_name.encode('ascii').hex()
    vm_prefix = 'e2e-watch-' + vm_key
    def evidence():
        try:
            return json.loads((tmp_path / 'evidence.json').read_text())
        except (OSError, ValueError):
            return {}
    wait(lambda: ui.showing('watch-window'), 'combined watcher opens')
    assert ui.showing('watch-waiting')
    control.write_text('ui')
    wait(lambda: evidence().get('run'), 'UI fixture starts')
    run = evidence()['run']
    wait(lambda: ui.showing(f'ui-watch-grid-{run}-test'), 'UI activity appears on All')
    try:
        wait(lambda: 'RUN OUTPUT' in ui.content('watch-output', maximum=10000), 'runner output is visible')
    except AssertionError:
        print('Watcher evidence:', evidence())
        print('Public terminal:', repr(ui.content('watch-output', maximum=10000)))
        raise
    wait(lambda: 'END WRAPPED' in ui.content('watch-output', maximum=10000), 'long terminal line wraps')
    wait(lambda: 'RUN PROGRESS' in ui.content('watch-output', maximum=10000), 'live runner dashboard appears')
    assert ui.text(f'ui-watch-grid-{run}-test') == 'UI first'
    control.write_text('both')
    wait(lambda: ui.showing(vm_prefix + '-progress'), 'VM viewer joins All')
    wait(lambda: ui.text(vm_prefix + '-progress') == 'VM first', 'VM progress is visible beside UI')
    assert ui.text(vm_prefix + '-title') == vm_name
    assert ui.text('watch-tab-' + vm_key) == vm_name
    assert ui.showing(f'ui-watch-grid-{run}-display') and ui.showing(vm_prefix + '-display')
    audit_owned_controls(ui, 'watch-window')
    control.write_text('split-check')
    wait(lambda: evidence().get('dividers_resized'), 'native column divider resizes')
    layout = evidence()
    assert .23 < layout['columns_ratio'] < .27
    assert layout['viewer_cells'] == {'ui-' + run: [0, 0, 1, 1], vm_key: [1, 0, 1, 1]}
    assert layout['icon'] == 'org.onpc.E2EWatch'
    assert (layout['no_horizontal_scroll'] and layout['terminal_readonly']
            and layout['terminal_colored'] and layout['terminal_selectable'])
    assert layout['terminal_columns'] < 60
    assert layout['wrap_repetitions'] * len('wrapped text ') > layout['terminal_columns']

    ui.activate('watch-tab-ui-' + run)
    wait(lambda: ui.showing('watch-page-ui-' + run), 'UI category tab opens')
    assert ui.showing(f'ui-watch-grid-{run}-test')
    control.write_text('hide-vm')
    wait(lambda: evidence().get('vm_frozen'), 'hidden VM stops rendering despite new publications')
    wait(lambda: 'FIX OUTPUT' in ui.content('watch-output', maximum=10000), 'fix-tests takes output priority')
    assert ui.text('watch-output-status') == 'Terminal Outputs — fix-tests'
    ui.activate('watch-tab-' + vm_key)
    wait(lambda: ui.showing('watch-page-' + vm_key), 'VM-only tab opens')
    wait(lambda: ui.text(vm_prefix + '-progress') == 'VM next', 'reactivated VM shows current state')
    control.write_text('hide-ui')
    wait(lambda: evidence().get('ui_frozen'), 'hidden UI stops updating despite new publications')
    ui.activate('watch-tab-all')
    wait(lambda: ui.showing(f'ui-watch-grid-{run}-test'), 'All restores its UI panel')
    wait(lambda: ui.text(f'ui-watch-grid-{run}-test') == 'UI next', 'All restores current UI state')
    control.write_text('vm-only')
    wait(lambda: ui.showing('watch-viewer-grid') and not ui.showing(f'ui-watch-grid-{run}-test'),
         'finished UI leaves VM at full height')
    wait(lambda: ui.text('watch-output-status') == 'Terminal Outputs — run-tests', 'runner resumes after repair')
    names = evidence()['vm_names']
    for count in (2, 3, 5):
        control.write_text('vms-' + str(count))
        expected = {name: [index % 2, index // 2, 1, 1]
                    for index, name in enumerate(names[:count])}
        wait(lambda: evidence().get('vm_cells') == expected,
             'active VMs occupy successive two-column cells')
        for name in names[:count]:
            prefix = 'e2e-watch-vm-' + name.encode('ascii').hex()
            assert ui.text(prefix + '-title') == name
        tabs = evidence()['vm_tabs']
        assert all(tabs[name] == 1 for name in names[:count])
        assert all(tabs[name] < .5 for name in names[count:])
    control.write_text('stall-vm')
    wait(lambda: evidence().get('stalled_vm_entered'), 'one VM transport stalls in its own worker')
    wait(lambda: ui.text(vm_prefix + '-progress') == 'Healthy during stall',
         'healthy VM keeps updating while another transport is stalled')
    wait(lambda: 'RUN WHILE VM STALLED' in ui.content('watch-output', maximum=10000),
         'terminal keeps updating while a VM transport is stalled')
    ui.activate('watch-tab-' + vm_key)
    wait(lambda: ui.showing('watch-page-' + vm_key), 'top tabs remain responsive during a stalled transport')
    ui.activate('watch-tab-all')
    control.write_text('release-vm')
    wait(lambda: evidence().get('stage') == 'release-vm' and
         len(evidence().get('vm_cells', {})) == 5, 'stalled VM recovers in the same grid')
    control.write_text('vms-3')
    wait(lambda: len(evidence().get('vm_cells', {})) == 3, 'three viewers reopen')
    control.write_text('double-click')
    third_key = 'vm-' + names[2].encode('ascii').hex()
    wait(lambda: ui.showing('watch-page-' + third_key), 'double click opens the cell VM tab')
    assert ui.text('e2e-watch-' + third_key + '-title') == names[2]
    ui.activate('watch-tab-all')
    control.write_text('vms-1')
    wait(lambda: len(evidence().get('vm_cells', {})) == 1, 'remaining VM fills All')
    control.write_text('unlocked')
    wait(lambda: evidence().get('vm_tabs', {}).get(vm_name, 1) < .5,
         'running VM becomes gray when its controller releases the lease')
    assert ui.showing(vm_prefix + '-display')
    assert evidence()['vm_cells'] == {vm_name: [0, 0, 1, 1]}
    control.write_text('idle')
    wait(lambda: ui.showing('watch-waiting'), 'both completed feeds leave watcher open')
    wait(lambda: ui.text('watch-output-status') == 'Terminal Outputs — run-tests (finished)',
         'completed terminal transcript remains available')
    wait(lambda: all(value < .5 for value in evidence().get('vm_tabs', {}).values()),
         'all idle VM tabs are gray')
    ui.activate('watch-tab-' + third_key)
    wait(lambda: ui.showing('watch-page-' + third_key), 'idle gray tab remains selectable')
    ui.activate('watch-close')
    wait(lambda: process.poll() is not None, 'closing viewer releases only its own resources')
    assert process.returncode == 0, log.read_text()
