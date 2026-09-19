"""Qualify the E2E public UI adapter against real GTK, outside the VM journey."""

import importlib.util
import json
import subprocess

import pytest

from tests.support.paths import ROOT
from tests.support.child_shell import run_child_shell

pytestmark = pytest.mark.ui


def test_installed_settings_users_publishes_builder_ids(hermetic_ui_session, tmp_path):
    """Qualify the installed GTK provider, not a project preview double."""
    log_path = tmp_path / 'gnome-control-center.log'
    with log_path.open('wb') as log:
        process = subprocess.Popen(
            ['/usr/bin/gnome-control-center', 'system', 'users'],
            env=hermetic_ui_session.environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            spec = importlib.util.spec_from_file_location(
                'e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            from gi.repository import Atspi, GLib
            ui = module.AccessibleUI(
                Atspi, timeout=10, query_errors=(GLib.Error,),
                dispatch=lambda: GLib.MainContext.default().iteration(False))
            for identity in ('split_view', 'search_button', 'search_bar',
                             'panel_list', 'navigation', 'current_user_page',
                             'user_list', 'add_user_button_row'):
                # This is an inventory of the provider's partial Builder IDs,
                # not a qualified interaction path. Some controls (notably the
                # search entry) are intentionally hidden until their identified
                # owner control is activated.
                assert ui.wait(
                    lambda identity=identity: [
                        node for node in ui.nodes()
                        if module.public_automation_id(node) == identity
                    ],
                    identity,
                )
            ui.activate(ui.id_target('search_button', sensitive=True))
            assert ui.wait(
                lambda: ui.find_id('search_entry', showing=False),
                'search_entry',
            )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


@pytest.mark.parametrize('dismissal', ['close', 'window-manager'])
def test_standard_user_startup_denial_has_specific_public_result(launch_ui, dismissal):
    spec = importlib.util.spec_from_file_location('e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application, _log = launch_ui('parent_component_preview', environment_overrides={
        'ONPC_PARENT_COMPONENT_SCENARIO': 'startup-denied'}, wait_for_application=False)
    from gi.repository import Atspi, GLib
    ui = module.AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui.management_denied()
    root = ui.id_target('parent-access-denied-window')
    assert ui.id_target('parent-access-denied-brand', root=root).get_name() == 'Oh No! Parent Control'
    assert ui.id_target('parent-access-denied-heading', root=root).get_name() == 'Administrator Required'
    if dismissal == 'close':
        ui.activate(ui.id_target('parent-access-denied-close', root=root))
    else:
        from dogtail import rawinput
        rawinput.keyCombo('<Alt>F4')
    ui.wait(lambda: ui.find_id('parent-access-denied-window') is None,
            'denial-dismissed')


@pytest.mark.usefixtures('hermetic_ui_session')
def test_search_adapter_in_isolated_shell(render_artifacts):
    import os
    import sys
    directory = render_artifacts('onpc-e2e-search-', parent='/tmp', shader_cache=True)
    result = run_child_shell({**os.environ,
        'ONPC_CHILD_SHELL_ARTIFACT_DIR': str(directory),
        'ONPC_CHILD_SHELL_PYTHON': sys.executable,
        'ONPC_CHILD_SHELL_SCENARIO': 'e2e-search',
        'ONPC_PREVIEW_READY_TIMEOUT_SECONDS': '30'}, timeout=90)
    assert result.returncode == 0, f'{directory}\n{result.stdout}\n{result.stderr}'
    assert 'e2e-search: provider-identity-blocked' in result.stdout


@pytest.mark.parametrize('dpi_scale', [1.0, 1.25])
def test_empty_parent_functional_adapter_at_display_scales(
        launch_ui, request_display_scale, dpi_scale):
    spec = importlib.util.spec_from_file_location('e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application, _log = launch_ui('parent_component_preview', environment_overrides={
        'ONPC_PARENT_COMPONENT_SCENARIO': 'no-users'}, wait_for_application=False)
    from gi.repository import Atspi, GLib
    ui = module.AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    try:
        assert ui.run('parent-empty', '') == {
            'operation': 'parent-empty', 'outcome': 'passed', 'interface': 'AT-SPI'}
    except Exception:
        print('Parent preview diagnostics:', _log)
        raise


@pytest.mark.parametrize('dpi_scale', [1.0, 1.25])
def test_parent_functional_adapter_at_display_scales(
        launch_ui, request_display_scale, dpi_scale):
    spec = importlib.util.spec_from_file_location('e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application, _log = launch_ui('parent_component_preview', wait_for_application=False)
    from gi.repository import Atspi, GLib
    ui = module.AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    version = json.loads((ROOT / 'data/app.json').read_text())['version']
    ui.fixture_uids = {module.CHILD: 1001, module.EXISTING_CHILD: 1002}
    try:
        opened = ui.run('child-picker-opened', version)
        from dogtail import rawinput
        assert opened['focused'] is True
        ui.run('child-choice-highlighted', version)
        rawinput.pressKey('Return')
        selected = ui.run('parent-selected', version)
        assert selected['settings']['child'] == 'fixture-child'
        opened = ui.run('discovery-child-picker-opened', version)
        assert opened['focused'] is True
        ui.run('discovery-child-choice-highlighted', version)
        rawinput.pressKey('Return')
        existing = ui.run('discovery-selected', version)
        assert existing['settings']['child'] == 'existing-fixture-child'
        ui.run('existing-apps', version)
        assert ui.run('discovery-ready', version)['settings'] == existing['settings']
        # Exercise the return picker as well; its highlight and final selection
        # are separate fresh observations even when the same child is chosen.
        opened = ui.run('existing-child-picker-opened', version)
        assert opened['focused'] is True
        ui.run('existing-child-choice-highlighted', version)
        rawinput.pressKey('Return')
        assert ui.run('existing-returned', version)['settings'] == existing['settings']
        opened = ui.run('child-picker-opened', version)
        assert opened['focused'] is True
        ui.run('child-choice-highlighted', version)
        rawinput.pressKey('Return')
        assert ui.run('parent-selected', version)['settings'] == selected['settings']
        # The allowance remains readable when the switch normally disables it.
        toggle = ui.id_target('parent-screen-limit-toggle', root=ui.parent())
        if ui.has_state(toggle, Atspi.StateType.CHECKED):
            ui.activate(toggle)
        ui.wait(lambda: not ui.has_state(toggle, Atspi.StateType.CHECKED), 'limit-off')
        disabled = ui.settings()
        assert not disabled['limit_enabled']
        assert disabled['allowance'] == selected['settings']['allowance']
        ui.run('about', version)
        ui.about_footer()
        ui.window_ready_to_close('about')
        rawinput.keyCombo('<Alt>F4')
        assert ui.run('parent-returned', version)['settings'] == disabled
    except Exception:
        print('Parent preview diagnostics:', _log)
        raise
