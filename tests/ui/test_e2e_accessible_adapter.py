"""Qualify the E2E public UI adapter against real GTK, outside the VM journey."""

import importlib.util
import json

import pytest

from tests.support.paths import ROOT
from tests.support.child_shell import run_child_shell

pytestmark = pytest.mark.ui


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
    assert 'e2e-search: typed-query-passed' in result.stdout


@pytest.mark.parametrize('dpi_scale', [1.0, 1.25])
def test_empty_parent_functional_adapter_at_display_scales(
        launch_ui, request_display_scale, dpi_scale):
    spec = importlib.util.spec_from_file_location('e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application, _log = launch_ui('parent_component_preview', environment_overrides={
        'ONPC_PARENT_COMPONENT_SCENARIO': 'no-users'})
    from gi.repository import Atspi, GLib
    ui = module.AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    try:
        assert ui.run('parent-empty', '') == {
            'operation': 'parent-empty', 'outcome': 'passed', 'interface': 'AT-SPI'}
    except Exception:
        from dogtail.hermetic.session import dump_tree
        print(dump_tree(application, max_depth=24))
        raise


@pytest.mark.parametrize('dpi_scale', [1.0, 1.25])
def test_parent_functional_adapter_at_display_scales(
        launch_ui, request_display_scale, dpi_scale):
    spec = importlib.util.spec_from_file_location('e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application, _log = launch_ui('parent_component_preview')
    from gi.repository import Atspi, GLib
    ui = module.AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    version = json.loads((ROOT / 'data/app.json').read_text())['version']
    try:
        opened = ui.run('child-picker-opened', version)
        from dogtail import rawinput
        for key in opened['navigation']:
            rawinput.pressKey(key.title())
        ui.run('child-choice-highlighted', version)
        rawinput.pressKey('Return')
        selected = ui.run('parent-selected', version)
        assert selected['settings']['child'] == 'fixture-child'
        opened = ui.run('discovery-child-picker-opened', version)
        for key in opened['navigation']:
            rawinput.pressKey(key.title())
        ui.run('discovery-child-choice-highlighted', version)
        rawinput.pressKey('Return')
        existing = ui.run('discovery-selected', version)
        assert existing['settings']['child'] == 'existing-fixture-child'
        ui.run('existing-apps', version)
        assert ui.run('discovery-ready', version)['settings'] == existing['settings']
        # Exercise the return picker as well; its highlight and final selection
        # are separate fresh observations even when the same child is chosen.
        opened = ui.run('existing-child-picker-opened', version)
        for key in opened['navigation']:
            rawinput.pressKey(key.title())
        ui.run('existing-child-choice-highlighted', version)
        rawinput.pressKey('Return')
        assert ui.run('existing-returned', version)['settings'] == existing['settings']
        opened = ui.run('child-picker-opened', version)
        for key in opened['navigation']:
            rawinput.pressKey(key.title())
        ui.run('child-choice-highlighted', version)
        rawinput.pressKey('Return')
        assert ui.run('parent-selected', version)['settings'] == selected['settings']
        # The allowance remains readable when the switch normally disables it.
        toggle = ui.target('Screen time limit', ('switch',), root=ui.parent())
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
        from dogtail.hermetic.session import dump_tree
        print(dump_tree(application, max_depth=24))
        raise
