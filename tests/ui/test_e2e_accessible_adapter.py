"""Qualify the E2E public UI adapter against real GTK, outside the VM journey."""

import copy
import importlib.util
import json

import gi
import pytest

gi.require_version('Atspi', '2.0')

from tests.support.paths import ROOT
from tests.support.child_shell import run_child_shell
from tests.support.automation_ids import audit_owned_controls

pytestmark = pytest.mark.ui


def _qualified_absent_prompt_contracts(module):
    """Describe the synthetic host session's known-absent prompt providers."""
    contracts = copy.deepcopy(module.EXTERNAL_PROVIDER_CONTRACTS)
    for provider, prefix, surface in (
            ('gnome-shell-polkit-agent', 'polkit', 'polkit'),
            ('gcr-keyring-prompter', 'keyring', 'keyring')):
        contracts[provider] = {
            'application_id': f'test-absent-{prefix}-application',
            'surfaces': {surface: (f'test-absent-{prefix}-dialog', {
                control: f'test-absent-{prefix}-{control}'
                for control in ('recipient', 'secret', 'confirm', 'cancel')
            })},
            'blocked_consumers': (),
        }
    return contracts


@pytest.mark.parametrize('profile', ['no-child', 'no-approver'])
def test_empty_station_adapter_reads_real_empty_form(
        launch_ui, automation, wait_for_accessible_state, tmp_path, profile):
    from tests.support.request_form import launch_request, calls
    from gi.repository import Atspi, GLib

    spec = importlib.util.spec_from_file_location('e2e_no_child_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Bind this maintained preview's finite labels/UIDs to the same sanitized
    # roles. Installed qualification retains the canonical VM fixture binding.
    module.APPROVER_IDENTITIES = {'Taylor Morgan': 'other-fixture-parent',
                                  'Avery Quinn': 'fixture-parent'}
    module.CHILD_IDENTITIES = {'Alex Morgan': 'existing-fixture-child'}
    _application, path = launch_request(
        launch_ui, tmp_path, overlay=False,
        scenario='no-children' if profile == 'no-child' else 'no-approvers')
    wait_for_accessible_state(lambda: automation.showing('kiosk-request-window'),
                              'empty station window')
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.KIOSK_APPLICATION,),
        application_owners=launch_ui.application_owners,
        fixture_uids={'Taylor Morgan': 1000, 'Avery Quinn': 1010, 'Alex Morgan': 1001},
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    for _ in range(2):
        result = ui.run(f'kiosk-{profile}-form', '')['request']
        assert result == {
            'surface': 'kiosk', 'form_count': 1,
            'child': 'none' if profile == 'no-child' else 'existing-fixture-child',
            'approver': 'other-fixture-parent' if profile == 'no-child' else 'none',
            'duration_seconds': 1800,
            'custom_text': None, 'allow_soft': False,
            'child_selector_enabled': True, 'approver_selector_enabled': False,
            'duration_enabled': False, 'soft_choice_enabled': False,
            'request_enabled': False, 'cancel_enabled': True,
            'message': profile, 'mute': None,
        }
    assert not calls(path, 'RequestAccess')


def test_approver_baseline_reads_real_disabled_form(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from tests.support.request_form import launch_request, calls
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    _application, path = launch_request(
        launch_ui, tmp_path, overlay=False, scenario='control-disabled-single-approver')
    wait_for_accessible_state(lambda: automation.showing('kiosk-screen-limit-notice'),
                              'disabled station loaded')
    assert not automation.state('kiosk-approver-selector', Atspi.StateType.SENSITIVE)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.KIOSK_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    result = ui.run('kiosk-approver-baseline', '')
    assert result['approver_uids'] == [1000]
    assert not calls(path, 'RequestAccess')


def test_station_restrictions_accept_real_request_controls(
        launch_ui, automation, wait_for_accessible_state, tmp_path, monkeypatch):
    from tests.support.request_form import launch_request, calls
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    # Uses the existing private preview, bus/display and launcher-owned process.
    # No shared resources or additional scheduling exclusion are needed.
    monkeypatch.setattr(module, 'CHILD_IDENTITIES', {'Alex Morgan': 'fixture-child'})
    monkeypatch.setattr(module, 'APPROVER_IDENTITIES', {
        'Taylor Morgan': 'fixture-parent', 'Avery Quinn': 'other-fixture-parent'})
    # The restriction leaf precedes FLOW04's child selection, so its entry
    # contract is the default disabled form, as in the installed journey.
    _application, path = launch_request(
        launch_ui, tmp_path, overlay=False, scenario='control-disabled')
    wait_for_accessible_state(lambda: automation.showing('kiosk-request-window'),
                              'request station loaded')
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.KIOSK_APPLICATION,),
        application_owners=launch_ui.application_owners,
        fixture_uids={'Taylor Morgan': 1000, 'Avery Quinn': 1010, 'Alex Morgan': 1001},
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    try:
        assert ui.kiosk_restrictions(stable_seconds=0)
    except module.UiError:
        # Synthetic host fixture only: record IDs/roles, never names or text.
        nodes, edges, identities, facts = ui.read_snapshot()
        window = ui.snapshot_matches('kiosk-request-window', nodes, identities=identities)
        print('Station public controls:', [
            (identities[node], facts[node]['role'])
            for node in ui.snapshot_scope(nodes, edges, window)
            if facts[node]['showing']])
        raise
    assert not calls(path, 'RequestAccess')


def _record_parent_public_state(ui, module, log_path):
    """Keep bounded public failure evidence without retrying customer input."""
    evidence = {'incomplete_reads': [], 'discarded_observations': ui.incomplete_observations}
    identities = (module.PARENT_APPLICATION, 'parent-window', 'about-dialog',
                  'parent-child-popover', 'parent-child-selected-1001',
                  'parent-child-selected-1002', 'parent-screen-limit-toggle',
                  'about-product-name', 'about-version', 'about-license-value')

    def snapshot():
        try:
            nodes = list(ui.nodes(strict=True))
            result = {}
            for identity in identities:
                matches = [node for node in nodes
                           if module.public_automation_id(node) == identity]
                result[identity] = [{
                    'showing': ui.showing(node),
                    'enabled': ui.has_state(node, ui.api.StateType.SENSITIVE),
                    'checked': ui.has_state(node, ui.api.StateType.CHECKED),
                    'defunct': ui.has_state(node, ui.api.StateType.DEFUNCT),
                    'surface': node.surface_id,
                    'parent_surface': node.surface_metadata.get('parent_id'),
                } for node in matches]
            evidence['complete_snapshot'] = result
            # Use the normal ownership reader independently of this diagnostic
            # traversal; recording a state never turns the failed test into a pass.
            evidence['parent_owner_valid'] = ui.find_id('parent-window') is not None
            evidence['about_owner_valid'] = ui.find_id('about-dialog') is not None
            return True
        except (*ui.query_errors, module.UiError) as error:
            evidence['incomplete_reads'].append({
                'error': str(error), 'notes': getattr(error, '__notes__', [])})
            return False

    try:
        ui.wait(snapshot, 'failure-public-state')
    except module.UiError as error:
        evidence['error'] = str(error)
    path = log_path.with_name('parent-public-state.json')
    path.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print('Parent public state:', path)


def test_feedback_read_adapter_uses_real_public_editor(launch_ui):
    from collections import Counter
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    launch_ui('parent_component_preview', wait_for_application=False)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.PARENT_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    expected = {'draft': 'initial-empty', 'attachments': ['diagnostic-logs.zip'],
                'collection': 'ready', 'validation': 'none', 'controls': 'ready'}
    try:
        for operation in ('feedback-open', 'feedback-read', 'feedback-close',
                          'feedback-wrong-entry', 'feedback-reopen',
                          'feedback-reread', 'feedback-finished'):
            result = ui.run(operation, '')
            if operation in ('feedback-open', 'feedback-read', 'feedback-reopen',
                             'feedback-reread'):
                assert result['feedback'] == expected
    except Exception:
        # This preview contains only declared synthetic data. Retain public-ID
        # collisions to diagnose toolkit internals without reading draft text.
        root = ui.id_target('feedback-dialog')
        counts = Counter(module.public_automation_id(node)
                         for node in ui.nodes(root, strict=True))
        print('Feedback duplicate public IDs:',
              {identity: count for identity, count in counts.items() if identity and count > 1})
        for identity in ('feedback-editor-input', 'feedback-reply-email'):
            count = len(ui.id_target(identity).getText())
            print('Synthetic field character count:', identity, count)
        raise


def test_existing_window_switch_entry_uses_public_owned_surfaces(launch_ui):
    # Reuses this module's private display/bus and fixture-owned preview process.
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    launch_ui('parent_component_preview', wait_for_application=False)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.PARENT_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui.id_target('parent-window')
    ui.wait(lambda: ui.existing_window_active('parent'), 'parent-active')
    assert ui.window_switch_proof('parent')['active'] is True
    with pytest.raises(module.UiError, match='switch-absent'):
        ui.window_switch_ready('feedback', 'parent')
    ui.run('feedback-open', '')
    root = ui.existing_window('feedback')
    assert ui.existing_window_active('feedback', expected=root) is not None
    with pytest.raises(module.UiError, match='switch-source'):
        ui.window_switch_ready('feedback', 'parent')


def test_format_adapter_reads_real_public_ranges(launch_ui):
    # Same private preview/display and owned-process fixture as the reviewed
    # adapter tests; no new shared resource or scheduler exclusion.
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    launch_ui('parent_component_preview', wait_for_application=False)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.PARENT_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    identity = 'feedback-editor-input'
    ui.run('feedback-open', '')
    ui.run('text-body-first-focus', '')
    ui.run('text-body-first-selected', '')
    ui.run('text-body-first-read', '')
    ui.run('format-before', '')
    ui.run('format-focus', '')
    ui.run('format-home', '')
    ui.run('format-selected', '')
    try:
        result = ui.run('format-read', '')['formatting']
    except module.UiError:
        # Only declared synthetic ranges and formats; no draft dump.
        from tests.e2e.block_semantics import document_runs
        for start, end, _text, attributes in document_runs(
                ui.text_recipient(identity), module.require):
            print('Synthetic public bold run:', start, end, bool(attributes.get('bold')))
        raise
    ui.run('format-close', '')
    ui.run('format-wrong-entry', '')
    assert ui.run('format-reopen', '')['formatting'] == result


def test_duplicate_adapter_builds_exact_formatting_fixture_by_application_ui(launch_ui):
    # Editing stays in the existing preview on this test's private bus.
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    launch_ui('parent_component_preview', wait_for_application=False)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.PARENT_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    identity = 'feedback-editor-input'
    ui.run('feedback-open', '')
    from tests.support.gui_blocks import run_block
    run_block(ui, 'complex')
    expected = {'bold': True, 'italic': True, 'underline': True, 'strike': True}
    def formats_match():
        from tests.e2e.block_semantics import document_runs
        ui.read_synthetic_text('body-complex')
        covered = 0
        for first, last, text, attributes in document_runs(
                ui.text_recipient(identity), module.require):
            if first >= len(module.COMPLEX_BODY):
                break
            # Quill stores inline formatting on characters, not the paragraph
            # newline; inspect every synthetic character independently.
            count = len(text.replace('\n', ''))
            if count and {key: bool(attributes.get(key)) for key in expected} != expected:
                return False
            covered += count
        return covered == module.COMPLEX_LINES
    ui.wait(formats_match, 'combined-formats')
    ui.rejection_formatting()
    ui.run('rejection-complex-send', '')
    assert ui.run('rejection-complex-read', '')['feedback_state']['validation'] == 'format-invalid'
    ui.run('rejection-close', '')
    ui.run('rejection-wrong-entry', '')
    ui.run('rejection-reopen', '')
    ui.run('rejection-reopened-send', '')
    assert ui.run('rejection-reopened-read', '')['feedback_state']['validation'] == 'format-invalid'
    # A public attribute must also disappear when its real format is removed.
    # These shorter valid drafts never reach Send.
    for kind in ('underline', 'strike'):
        ui.run(f'rejection-format-{kind}-focus', '')
        ui.run(f'rejection-format-{kind}-apply', '')
        expected[kind] = False
        ui.wait(formats_match, 'removed-format')


def test_length_adapter_reads_full_ascii_and_non_bmp_boundaries(launch_ui):
    # Existing owned preview/private display and bus; editor text and Unicode
    # scalars use the same fixed public editing operations as installed cases.
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module
    launch_ui('parent_component_preview', wait_for_application=False)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.PARENT_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    from tests.support.gui_blocks import run_block
    ui.run('feedback-open', '')
    for family in ('ascii', 'mixed'):
        observations = run_block(ui, 'length', family)
        state = observations[f'length-{family}-valid']['feedback_state']
        assert state['validation'] == 'none' and state['send_enabled']
        state = observations[f'rejection-{family}-read']['feedback_state']
        assert state['validation'] == 'length-invalid' and state['send_enabled']
        ui.run(f'length-{family}-close', '')
        ui.run(f'length-{family}-wrong-entry', '')
        state = ui.run(f'length-{family}-reopen', '')['feedback_state']
        assert state['draft'] == f'length-{family}-5001'
        ui.run(f'rejection-{family}-reopened-send', '')
        assert ui.run(f'rejection-{family}-reopened-read', '')['feedback_state']['validation'] == 'length-invalid'
        if family == 'ascii':
            ui.run('length-ascii-close', '')
            assert ui.run('length-ascii-reopen', '')['feedback_state']['validation'] == 'none'


def test_rejection_adapter_reads_real_empty_and_malformed_explanations(launch_ui):
    # Existing private preview/display and owned cleanup; no additional shared
    # resources. Only proven invalid bodies/replies reach the real Send control.
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    launch_ui('parent_component_preview', wait_for_application=False)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.PARENT_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui.run('feedback-open', '')
    ui.run('rejection-empty-send', '')
    assert ui.run('rejection-empty-read', '')['feedback_state']['validation'] == 'body-required'
    for binding in ('body-first', 'reply-malformed'):
        identity, value = module.TEXT_VALUES[binding]
        if binding.startswith('reply-'):
            ui.run(f'text-{binding}-anchor', '')
        ui.run(f'text-{binding}-focus', '')
        ui.run(f'text-{binding}-selected', '')
        ui.run(f'text-{binding}-read', '')
        if binding == 'body-first':
            ui.run('rejection-valid-refusal', '')
    ui.run('rejection-malformed-send', '')
    assert ui.run('rejection-malformed-read', '')['feedback_state']['validation'] == 'reply-invalid'


def test_text_replacement_adapter_uses_real_body_and_native_reply(launch_ui):
    from gi.repository import Atspi, GLib
    from tests.e2e import accessible_ui as module

    launch_ui('parent_component_preview', wait_for_application=False)
    ui = module.AccessibleUI(
        Atspi, timeout=20, query_errors=(GLib.Error,),
        application_ids=(module.PARENT_APPLICATION,),
        application_owners=launch_ui.application_owners,
        provider_contracts=_qualified_absent_prompt_contracts(module),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui.run('feedback-open', '')
    # Preserve the original replacement/clear slice as the registry grows.
    bindings = {binding: target for binding, target in module.TEXT_VALUES.items()
                if binding in ('body-first', 'body-second', 'body-clear',
                               'reply-first', 'reply-second', 'reply-clear')}
    assert len(bindings) == 6

    from tests.support.gui_blocks import run_block

    def replace(binding):
        value = module.TEXT_VALUES[binding][1]
        result = run_block(ui, 'replace', binding)
        assert result[f'text-{binding}-read']['text'] == {
            'binding': binding, 'exact': True, 'length': len(value)}

    for binding in bindings:
        if binding == 'reply-first':
            ui.run('feedback-close', '')
            ui.run('feedback-reopen', '')
        replace(binding)
    # FEED09 uses the same private preview and public editing operations; no new
    # processes/displays or shared resources beyond this reviewed UI fixture.
    assert ui.run('feedback-state-empty', '')['feedback_state']['send_enabled'] is True
    for binding, operation in (
            ('body-whitespace', 'feedback-state-whitespace'),
            ('body-first', 'feedback-state-no-reply'),
            ('reply-malformed', 'feedback-state-malformed'),
            ('reply-first', 'feedback-state-valid')):
        replace(binding)
        state = ui.run(operation, '')['feedback_state']
        assert state['validation'] == 'none' and state['send_enabled'] is True
    ui.run('feedback-state-close', '')
    ui.run('feedback-state-wrong-entry', '')
    assert ui.run('feedback-state-reopen', '')['feedback_state'] == state
    replace('body-clear')
    replace('reply-clear')
    ui.run('feedback-finished', '')


@pytest.mark.parametrize('dismissal', ['close', 'window-manager'])
def test_standard_user_startup_denial_has_specific_public_result(launch_ui, automation,
                                                               wait_for_accessible_state, dismissal):
    spec = importlib.util.spec_from_file_location('e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    launch_ui('kiosk_preview', wait_for_application=False)
    wait_for_accessible_state(lambda: automation.showing('kiosk-request-window'),
                              'positive surrounding preview surface')
    application, _log = launch_ui('parent_component_preview', environment_overrides={
        'ONPC_PARENT_COMPONENT_SCENARIO': 'startup-denied'}, wait_for_application=False)
    from gi.repository import Atspi, GLib
    ui = module.AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                            application_ids=(module.PARENT_APPLICATION,),
                            application_owners=launch_ui.application_owners,
                            provider_contracts=_qualified_absent_prompt_contracts(module),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui.management_denied()
    root = ui.id_target('parent-access-denied-window')
    assert audit_owned_controls(
        ui, 'parent-access-denied-window', root=root,
    )
    assert ui.id_target('parent-access-denied-brand', root=root).get_name() == 'Oh No! Parent Control'
    assert ui.id_target('parent-access-denied-heading', root=root).get_name() == 'Administrator Required'
    if dismissal == 'close':
        ui.activate_id('parent-access-denied-close')
    else:
        ui.close_id('parent-access-denied-window')
    ui.wait(lambda: automation.absent('parent-access-denied-window', within='kiosk-request-window'),
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
                            application_ids=(module.PARENT_APPLICATION,),
                            application_owners=launch_ui.application_owners,
                            provider_contracts=_qualified_absent_prompt_contracts(module),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    try:
        assert ui.run('parent-empty', '') == {
            'operation': 'parent-empty', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    except Exception:
        print('Parent preview diagnostics:', _log)
        raise


def test_parent_checked_api_observer_around_public_toggle(launch_ui, monkeypatch):
    """Public API result observation with the ordinary UI17 setter as caller."""
    from gi.repository import Atspi, GLib
    spec = importlib.util.spec_from_file_location('e2e_event_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    launch_ui('parent_component_preview', wait_for_application=False)
    def observer():
        return module.AccessibleUI(Atspi, timeout=20, query_errors=(GLib.Error,),
            application_ids=(module.PARENT_APPLICATION,),
            application_owners=launch_ui.application_owners,
            fixture_uids={module.CHILD: 1001, module.EXISTING_CHILD: 1002},
            provider_contracts=_qualified_absent_prompt_contracts(module),
            dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui = observer()
    ui.run('child-picker-opened', '')
    ui.run('child-choice-highlighted', '')
    ui.run('parent-selected', '')
    ui.parent_toggle_operation('parent-toggle-disabled')
    ui.parent_save_snapshot(module.CHILD, False)
    ui.trace_request, ui.trace_boot = 'a' * 32, 'b' * 64
    calls = []
    def ready(line, **kwargs):
        value = json.loads(line)
        assert value['event'] == 'accessibility-trace-ready'
        assert not calls
        calls.append(value)
        actor = observer()
        actor.expected_trace_source = value['source']
        assert actor.parent_toggle_operation('parent-toggle-enabled') == {
            'state': True, 'activated': True}
    monkeypatch.setattr(module, 'print', ready, raising=False)
    result = ui.parent_checked_events('parent-checked-events')
    assert result['samples'] and all(sample['source'] == 'application-ui'
                                     for sample in result['samples'])
    assert result['samples'][-1]['checked'] is True and len(calls) == 1
    assert observer().parent_save_snapshot(module.CHILD, True)['result'] == 'saved'


@pytest.mark.parametrize('dpi_scale', [1.0, 1.25])
def test_parent_functional_adapter_at_display_scales(
        launch_ui, request_display_scale, dpi_scale):
    spec = importlib.util.spec_from_file_location('e2e_accessible_ui', ROOT / 'tests/e2e/accessible_ui.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application, _log = launch_ui('parent_component_preview', wait_for_application=False)
    from gi.repository import Atspi, GLib
    ui = module.AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                            timing=lambda value: print(json.dumps(value, sort_keys=True), flush=True),
                            application_ids=(module.PARENT_APPLICATION,),
                            application_owners=launch_ui.application_owners,
                            provider_contracts=_qualified_absent_prompt_contracts(module),
                            dispatch=lambda: GLib.MainContext.default().iteration(False))
    version = json.loads((ROOT / 'data/app.json').read_text())['version']
    ui.fixture_uids = {module.CHILD: 1001, module.EXISTING_CHILD: 1002}
    try:
        ui.run('child-picker-opened', version)
        assert set(ui.id_target('parent-child-selector').getChoices()) == {'1001', '1002'}
        ui.run('child-choice-highlighted', version)
        selected = ui.run('parent-selected', version)
        assert selected['settings']['child'] == 'fixture-child'
        ui.run('parent-page-wrong-child-refused', version)
        import hashlib
        expected_rows = tuple(sorted(
            ('parent-app-' + hashlib.sha256(identity.encode()).hexdigest()[:16], access, match)
            for identity, access, match in (
                ('thunderbird_thunderbird.desktop', 'allowed', 'precise'),
                ('lunarclient.desktop', 'permanent', 'pattern'),
                ('com.mojang.Minecraft.desktop', 'conditional', 'precise'),
                ('steam.desktop', 'conditional', 'precise'))))
        for _ in range(2):
            before = ui.run('parent-selected', version)['settings']
            ui.run('parent-apps-page', version)
            assert ui.run('parent-app-rows', version)['apps']['rows'] == expected_rows
            assert ui.run('parent-app-rows-wrong-child', version)['apps'] == {'refusal': 'wrong-child'}
            assert ui.run('parent-app-rows-wrong-page', version)['apps'] == {'refusal': 'wrong-page'}
            assert ui.run('parent-app-rows-reopened', version)['apps']['rows'] == expected_rows
            assert ui.run('parent-screen-page', version)['settings'] == before
        ui.run('discovery-child-picker-opened', version)
        ui.run('discovery-child-choice-highlighted', version)
        existing = ui.run('discovery-selected', version)
        assert existing['settings']['child'] == 'existing-fixture-child'
        ui.run('existing-apps', version)
        assert ui.run('discovery-ready', version)['settings'] == existing['settings']
        # Choosing the same child again preserves that child's saved policy.
        ui.run('existing-child-picker-opened', version)
        ui.run('existing-child-choice-highlighted', version)
        assert ui.run('existing-returned', version)['settings'] == existing['settings']
        ui.run('child-picker-opened', version)
        ui.run('child-choice-highlighted', version)
        assert ui.run('parent-selected', version)['settings'] == selected['settings']
        # The allowance remains readable when the switch normally disables it.
        toggle = ui.id_target('parent-screen-limit-toggle', root=ui.parent())
        if ui.has_state(toggle, Atspi.StateType.CHECKED):
            ui.activate_id('parent-screen-limit-toggle')
        ui.wait(lambda: not ui.id_target('parent-screen-limit-toggle').getValue(), 'limit-off')
        disabled = ui.settings()
        assert not disabled['limit_enabled']
        assert disabled['allowance'] == selected['settings']['allowance']
        # INFO01 Parent composes the same ID-owned readers used by installed
        # qualification. This private preview adds no processes or shared state.
        ui.run('parent-help-clickable', version)
        ui.run('parent-information-about', version)
        for _ in range(2):
            ui.run('parent-information-clickable', version)
        if ui.incomplete_observations:
            _record_parent_public_state(ui, module, _log)
        ui.about_footer()
        ui.window_ready_to_close('about')
        ui.close_id('about-dialog')
        assert ui.run('parent-returned', version)['settings'] == disabled
    except Exception:
        print('Parent preview diagnostics:', _log)
        _record_parent_public_state(ui, module, _log)
        raise
