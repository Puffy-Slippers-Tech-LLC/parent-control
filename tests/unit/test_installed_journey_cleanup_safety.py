"""Shared installed controller with real durable recorder; no VM operations."""

from dataclasses import replace
import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import evidence
import installed_journey as journeys
import installed_setup
import parent_about
import parent_information
import real_interval
import real_interval_qualification
import parent_access
import parent_terminal
import command_help
import command_documentation
import session_control
import desktop_session
import kiosk_entry
import kiosk_eligible_choices
import kiosk_valid_duration
import request_duration
import request_flow
import restricted_station_about
import kiosk_about
import overlay_about
import mate_prompt
import overlay_prompt
import overlay_approved_exit
import kiosk_multiple
import kiosk_approval
import auth_result
import kiosk_approved_flow
import kiosk_rejection
import approval_flow


@pytest.mark.parametrize('failure', [0, 1])
def test_flow07_selector_runs_separate_owned_attempts_and_stops_after_failure(monkeypatch, failure):
    import check_e2e_approval_flow as selector
    smoke = Mock(side_effect=[failure, 0])
    monkeypatch.setattr(selector, 'smoke', smoke)
    monkeypatch.setattr(selector, 'named_input', lambda: 'owned-input')
    assert selector.main() == failure
    assert [call.kwargs for call in smoke.call_args_list] == [
        dict(assets='owned-input', provision_credentials=True, approval_flow=outcome)
        for outcome in (('rejection',) if failure else ('rejection', 'cancel'))]
import restricted_station


@pytest.mark.parametrize('selector,mode', [('auth_prompt', 'mate_prompt'),
                                          ('read_restricted_station_about', 'restricted_station_about'),
                                          ('kiosk_multiple', 'kiosk_multiple'),
                                          ('kiosk_approval', 'kiosk_approval'),
                                          ('auth_result', 'auth_result'),
                                          ('kiosk_approved_flow', 'kiosk_approved_flow'),
                                          ('kiosk_rejection', 'kiosk_rejection')])
def test_auth_prompt_qualification_reuses_owned_mate_envelope(selector, mode):
    # The argument-free selector must not acquire a separate VM/cleanup route.
    import ast
    source = (ROOT / ('tests/integration/check_e2e_' + selector + '.py')).read_text()
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'smoke']
    assert len(calls) == 1
    keywords = {item.arg: ast.unparse(item.value) for item in calls[0].keywords}
    assets = ('named_input(package_source=True)' if selector in ('kiosk_approval', 'kiosk_approved_flow')
              else 'named_input()')
    assert keywords == {'assets': assets, 'provision_credentials': 'True',
                        mode: 'True'}
import kiosk_cancel
import kiosk_escape
import kiosk_approved
import kiosk_no_child
import kiosk_no_approver
import request_choices
import request_exit
import parent_toggle
import app_row_observations
import native_fixture_qualification
import native_grid_usable
import native_app
import catalogue_search
import catalogue
import policy_legend
import match_save_cancel
import rejected_parent_rule
import access_choices
import policy_qualification
from match_rules import MatchRuleJourney
import search_filters
import feedback_read
import feedback_privacy
import feedback_states
import trace_stable_state
import trace_transition
import compose_observation
import accessibility_input_trace
import format_qualification
import feedback_block_semantics
import feedback_formats_qualification
import feedback_rejection
import feedback_length
import window_switch
import text_qualification
import named_child_custom_saves
import allowance_presets
import allowance
import time_explanation
import fresh_thirty_allowance
import parent_discovery
import shell_search_results
import parent_search_launch
import parent_terminal_provider
import license_viewer_provider
import repeated_operations
import challenges
import fresh_child_allowed
import fresh_child_denied
import countdown_qualification
import shell_panel
import shell_search
import accessible_ui
import inventory
from private_artifacts import EvidenceError, PrivateCollector
from recording import ScenarioRecorder
from tests.support.paths import ROOT


SYNTHETIC = journeys.JourneyPlan(
    prefix='example', worker_mode='example_view',
    screen_tags={'installed-greeter': 'onpc-example-greeter', 'opened': 'onpc-example-opened',
                 'details': 'onpc-example-details', 'returned': 'onpc-example-opened'},
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            'opened': 'step-1', 'details': 'step-1', 'returned': 'step-2'},
    advance_after={'details': 'step-2'},
)

INTERVAL_RECORDER_PLAN = replace(real_interval_qualification.PLAN,
    advance_after={'before': 'step-2'},
    phases={**real_interval_qualification.PLAN.phases, 'after': 'step-2'})


@pytest.fixture
def journey_inventory():
    # Read-only template: each case copies only its family before mutation.
    # Avoid writing the entire customer catalogue for every recorder fault.
    return inventory.read_json(ROOT / 'tests/e2e/scenarios.json')[0]


def test_shared_system_prompt_coordinate_rendezvous_refuses_before_files_or_guard(tmp_path):
    journey = journeys.InstalledJourney(
        SimpleNamespace(directory=tmp_path), Mock(), parent_access.PLAN)
    guard = Mock(side_effect=AssertionError('guard must not run'))
    with pytest.raises(EvidenceError, match='prompt-coordinate-route-refused'):
        journey.dismiss_system_prompt('app-grid', {'x': 200, 'y': 330}, guard)
    guard.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('operation', ['desktop', 'fresh-parent-desktop', 'standard-desktop',
                                       'fresh-standard-desktop', 'parent-selected'])
@pytest.mark.parametrize('fault', [None, 'ui', 'boot', 'preparation'])
def test_parent_desktop_preparation_is_shared_durable_and_fail_closed(
        tmp_path, monkeypatch, operation, fault):
    plan = replace(SYNTHETIC, screen_tags={'entry': 'ui:' + operation},
                   phases={'ready': 'setup', 'setup-detached': 'setup', 'entry': 'step-1'},
                   advance_after={})
    progress = Mock()
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
    journey.boot = 'a' * 64
    journey.transport = object()
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
    journey.ui = SimpleNamespace(
        boot_proof=('b' if fault == 'boot' else 'a') * 64,
        observe=Mock(return_value=result, side_effect=RuntimeError('ui-failed') if fault == 'ui' else None))
    preparation = {'operation': 'parent-continuous-activity', 'outcome': 'passed',
                   'interface': 'system session', 'idle_delay_seconds': 0,
                   'previous_idle_delay_seconds': 300}
    prepare = Mock(return_value=preparation,
                   side_effect=RuntimeError('prepare-failed') if fault == 'preparation' else None)
    monkeypatch.setattr(session_control, 'observe', prepare)
    (tmp_path / 'entry.request.json').write_text(json.dumps({'stage': 'entry', 'screenshot': None}))
    parent = operation in ('desktop', 'fresh-parent-desktop')
    if fault in ('ui', 'boot') or fault == 'preparation' and parent:
        with pytest.raises((RuntimeError, EvidenceError)):
            journey.step(Mock())
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
        progress.assert_not_called()
        assert not (tmp_path / 'entry.reply.json').exists()
    else:
        def recorded(stage, observed):
            assert stage == 'entry'
            assert not (tmp_path / 'entry.reply.json').exists()
            assert observed.get('desktop_preparation') == (preparation if parent else None)
        progress.side_effect = recorded
        journey.step(Mock())
        progress.assert_called_once()
        assert (tmp_path / 'entry.reply.json').exists()
    if parent and fault not in ('ui', 'boot'):
        prepare.assert_called_once_with(journey.transport, 'parent-continuous-activity')
    else:
        prepare.assert_not_called()


@pytest.mark.parametrize('plan', [parent_about.PLAN, SYNTHETIC, parent_discovery.PLAN,
                                 parent_discovery.EMPTY_PLAN, parent_access.PLAN, parent_terminal.PLAN,
                                 command_help.PLAN, desktop_session.LOGOUT_PLAN,
                                 desktop_session.SWITCH_PLAN, kiosk_entry.PLAN,
                                 request_exit.PLAN, parent_toggle.PLAN, kiosk_eligible_choices.PLAN,
                                 request_choices.PLAN, kiosk_no_child.PLAN, kiosk_no_child.CASE_PLAN,
                                 kiosk_no_approver.PLAN, kiosk_no_approver.CASE_PLAN,
                                 parent_terminal_provider.PLAN, license_viewer_provider.PLAN,
                                 license_viewer_provider.WEBSITE_PLAN,
                                 license_viewer_provider.PRIVACY_PLAN,
                                 license_viewer_provider.SUPPORT_PLAN,
                                 license_viewer_provider.INFORMATION_PLAN,
                                 parent_information.PLAN,
                                 repeated_operations.PLAN, challenges.PLAN, fresh_child_allowed.PLAN,
                                 fresh_child_denied.PLAN, countdown_qualification.PLAN,
                                 countdown_qualification.OFF_PLAN, shell_panel.PLAN, app_row_observations.PLAN,
                                 native_fixture_qualification.PLAN,
                                 native_grid_usable.PLAN, native_app.PLAN,
                                 catalogue_search.PLAN,
                                 catalogue.PLAN,
                                 policy_legend.PLAN,
                                 match_save_cancel.PLAN,
                                 match_save_cancel.EDITOR_PLAN,
                                 rejected_parent_rule.PLAN,
                                 access_choices.PLAN,
                                 policy_qualification.PLAN,
                                 search_filters.PLAN,
                                 feedback_read.PLAN, feedback_privacy.PLAN, feedback_states.PLAN,
                                 trace_stable_state.PLAN, trace_transition.PLAN, compose_observation.PLAN,
                                 accessibility_input_trace.PLAN, named_child_custom_saves.PLAN,
                                 format_qualification.PLAN, feedback_block_semantics.PLAN,
                                 feedback_formats_qualification.PLAN,
                                 feedback_formats_qualification.LINK_PLAN,
                                 feedback_rejection.PLAN, feedback_length.PLAN,
                                 window_switch.PLAN,
                                 text_qualification.PLAN, allowance_presets.PLAN,
                                 allowance.PLAN, time_explanation.PLAN, kiosk_valid_duration.PLAN,
                                 request_duration.PLAN, request_flow.PLAN, kiosk_cancel.PLAN,
                                 kiosk_escape.PLAN, kiosk_approved.PLAN, mate_prompt.PLAN, kiosk_approval.PLAN,
                                 kiosk_rejection.PLAN, auth_result.PLAN, kiosk_approved_flow.PLAN,
                                 restricted_station.PLAN, approval_flow.REJECTION_PLAN, approval_flow.CANCEL_PLAN,
                                 kiosk_multiple.PLAN, kiosk_multiple.CASE_PLAN,
                                 kiosk_multiple.INELIGIBLE_PLAN, kiosk_multiple.INELIGIBLE_CASE_PLAN,
                                 restricted_station_about.PLAN, fresh_thirty_allowance.PLAN,
                                 fresh_thirty_allowance.JORDAN_PLAN, kiosk_about.PLAN, overlay_about.PLAN,
                                 overlay_prompt.PLAN, overlay_approved_exit.PLAN, INTERVAL_RECORDER_PLAN],
                         ids=['parent', 'different-consumer', 'discovery', 'empty',
                              'standard-access', 'terminal', 'help', 'desktop-logout',
                              'desktop-switch', 'kiosk-entry', 'request-exit', 'parent-toggle',
                              'kiosk-eligible-choices', 'request-choices', 'kiosk-no-child', 'no-child-case',
                              'kiosk-no-approver', 'no-parent-case',
                              'terminal-provider', 'license-viewer-provider', 'parent-website',
                              'parent-privacy', 'parent-support', 'parent-information', 'parent-links',
                              'repeated-operations',
                              'challenges', 'fresh-child-allowed', 'fresh-child-denied',
                              'countdown-enabled', 'countdown-off', 'shell-panel', 'app-rows', 'native-fixtures', 'native-grid-usable', 'native-app', 'catalogue-search', 'catalogue', 'policy-legend', 'match-save-cancel', 'match-editor', 'rejected-parent-rule', 'access-choices', 'policy', 'search-filters', 'feedback-read', 'feedback-privacy', 'feedback-states',
                              'trace-stable', 'trace-transition', 'compose-observation',
                              'accessibility-trace', 'named-child-custom-saves',
                              'format', 'block-semantics', 'feedback-formats', 'feedback-link',
                              'feedback-rejection', 'feedback-length', 'window-switch',
                              'text', 'allowance-presets',
                              'allowance', 'time-explanation', 'kiosk-valid-duration', 'request-duration',
                              'request-flow', 'kiosk-cancel', 'kiosk-escape', 'kiosk-approved-case', 'mate-prompt', 'kiosk-approval',
                              'kiosk-rejection', 'auth-result', 'kiosk-approved-flow', 'restricted-station',
                              'flow-rejection', 'flow-cancel', 'kiosk-multiple', 'multiple-case',
                              'ineligible-profile', 'ineligible-case', 'station-about', 'fresh-thirty-allowance',
                              'jordan-thirty-allowance', 'station-about-case', 'overlay-about-case', 'overlay-prompt', 'overlay-approved-exit', 'real-interval'])
@pytest.mark.parametrize('failure', [None, 'observation-write', 'return-step-write', 'worker-loss'])
def test_shared_plan_records_before_input_and_latches_transition_failures(
        tmp_path, monkeypatch, journey_inventory, plan, failure):
    # A different trusted plan exercises the same recorder phase shape without
    # registering a synthetic scenario or awarding it any customer coverage.
    selector = ('E2E-003/existing-and-new' if plan is parent_discovery.PLAN else 'E2E-030/parent')
    if plan is parent_discovery.EMPTY_PLAN:
        selector = 'E2E-003/none'
    if plan is parent_access.PLAN:
        selector = 'E2E-004/app-grid'
    if plan in (parent_terminal.PLAN, parent_terminal_provider.PLAN):
        selector = 'E2E-004/terminal'
    if plan is command_help.PLAN:
        selector = 'E2E-042/command-help'
    if plan is kiosk_about.PLAN:
        selector = 'E2E-042/kiosk'
    if plan is overlay_about.PLAN:
        selector = 'E2E-042/child-overlay'
    if plan is search_filters.PLAN:
        selector = 'E2E-041/search-filters'
    if plan is parent_information.PLAN:
        selector = 'E2E-042/parent-links'
    if plan is kiosk_no_child.CASE_PLAN:
        selector = 'E2E-017/no-child'
    if plan is kiosk_no_approver.CASE_PLAN:
        selector = 'E2E-017/no-parent'
    if plan is kiosk_multiple.CASE_PLAN:
        selector = 'E2E-017/multiple'
    if plan is kiosk_multiple.INELIGIBLE_CASE_PLAN:
        selector = 'E2E-017/ineligible-parent'
    if plan is kiosk_cancel.PLAN:
        selector = 'E2E-015/kiosk-cancel'
    if plan is kiosk_escape.PLAN:
        selector = 'E2E-015/kiosk-escape'
    if plan is kiosk_approved.PLAN:
        selector = 'E2E-015/kiosk-approved'
    if plan is restricted_station.PLAN:
        selector = 'E2E-016/approved'
    scenario_id, variant_id = selector.split('/', 1)
    document = {**journey_inventory, 'scenarios': [copy.deepcopy(next(
        scenario for scenario in journey_inventory['scenarios'] if scenario['id'] == scenario_id))]}
    selected = next(
        variant
        for scenario in document['scenarios'] if scenario['id'] == scenario_id
        for variant in scenario['variants'] if variant['id'] == variant_id
    )
    selected.update(
        status='ready', pending_reason=None,
        executable={'path': 'tests/e2e/installed_journey.py',
                    'test_id': 'synthetic-recorder-safety'},
    )
    if plan.assertions_after:
        scenario = next(s for s in document['scenarios'] if s['id'] == scenario_id)
        scenario['assertions']['visible'] = [
            {'id': assertion, 'step_id': plan.phases[stage], 'description': 'Independent return.'}
            for stage, assertion in plan.assertions_after.items()]
    inventory_path = tmp_path / 'scenarios.json'
    inventory_path.write_text(json.dumps(document))
    inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in evidence.INPUT_FIELDS}
    inputs.update(inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
                  environment_id='ubuntu26-04-pinned')
    contract = evidence.EvidenceContract(inventory_path=inventory_path, root=ROOT,
        selector=selector, run_id='shared-controller-test', inputs=inputs)
    directory = tmp_path / 'raw'
    directory.mkdir()
    (directory / 'testresults').mkdir()
    details = []
    for index, (stage, tag) in enumerate(plan.screen_tags.items()):
        details.extend([
            {'needle': tag, 'result': 'ok', 'area': [{'result': 'ok', 'similarity': 100}],
             'screenshot': f'smoke-{index}.png'},
            {'title': plan.prefix + '-' + stage, 'result': 'ok'},
        ])
    (directory / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
    monkeypatch.setattr(journeys, 'screenshot', lambda *_: {'sha256': 'a' * 64})
    monkeypatch.setattr(journeys.system, 'address', Mock(return_value='fixture-host'))
    monkeypatch.setattr(journeys, 'Transport', Mock())
    setup = Mock(return_value={'package_verified': True, 'setup_reboot_verified': True})
    provision = Mock()
    monkeypatch.setattr(installed_setup, 'InstalledSetup',
                        Mock(return_value=SimpleNamespace(run=setup, provision=provision)))
    boot = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    monkeypatch.setattr(journeys, 'ReadOnlyObservations', Mock(return_value=boot))
    operation_counts = {}
    boot_bindings = []

    def observe_ui(operation, *, child=None):
        import accessible_ui
        if child is not None:
            assert plan.child_bindings[state['stage']] == child
        assert ui_observer.boot_guard == ('b' * 64 if boot_bindings or boot.read.call_count else '')
        boot_bindings.append(ui_observer.boot_guard)
        operation_counts[operation] = operation_counts.get(operation, 0) + 1
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'about-interval-read':
            result['about_interval'] = {'pid': 123, 'endpoint': [':1.2', '/about'],
                                        'product': accessible_ui.PRODUCT, 'version': '9.8.7'}
        if operation == 'station-entry-branch':
            result['branch'] = {'destination': 'default-request-form', 'controls': []}
        if operation == 'station-default-entry':
            result['entry'] = {'destination': 'default-request-form'}
        if operation in accessible_ui.SETTINGS_OPERATIONS:
            result['settings'] = {'child': accessible_ui.CHILD_IDENTITIES[
                accessible_ui.SETTINGS_OPERATIONS[operation]], 'limit_enabled': False,
                'allowance': ['1 hour'] if operation.startswith('new-') else ['0 minutes']}
            if plan is repeated_operations.PLAN and (
                    operation == 'parent-selected' and operation_counts[operation] == 3
                    or operation == 'parent-screen-page' and operation_counts[operation] == 2):
                result['settings']['allowance'] = ['1 hour']
            if plan in (fresh_thirty_allowance.PLAN, fresh_thirty_allowance.JORDAN_PLAN) and state['stage'] == 'final-settings':
                result['settings'].update(limit_enabled=True, allowance=['30 minutes'])
            if plan is search_filters.PLAN and state['stage'] == 'saved-settings':
                result['settings'].update(limit_enabled=True, allowance=['30 minutes'])
            if plan is named_child_custom_saves.PLAN and state['stage'] in plan.settings_checks:
                expected = plan.settings_checks[state['stage']]
                result['settings'].update(child=expected.child, limit_enabled=expected.limit_enabled,
                                          allowance=list(expected.allowance))
        if (operation in accessible_ui.KIOSK_OPERATIONS
                or operation in accessible_ui.KIOSK_ACCOUNT_REQUESTS
                or operation in accessible_ui.KIOSK_DISABLED_REQUESTS
                or operation == 'overlay-request-form'):
            result['request'] = {
                'surface': 'kiosk', 'form_count': 1, 'child': 'existing-fixture-child',
                'approver': 'other-fixture-parent', 'duration_seconds': 1800,
                'custom_text': None, 'allow_soft': False,
                'child_selector_enabled': True, 'approver_selector_enabled': False,
                'duration_enabled': False, 'soft_choice_enabled': False,
                'request_enabled': False, 'cancel_enabled': True,
                'message': 'screen-limit-disabled', 'mute': None,
            }
            if operation in accessible_ui.KIOSK_ACCOUNT_REQUESTS:
                child, approver = accessible_ui.KIOSK_ACCOUNT_REQUESTS[operation]
                result['request'].update(child=child, approver=approver,
                    approver_selector_enabled=True, duration_enabled=True,
                    soft_choice_enabled=True, request_enabled=True, message='')
            if operation in accessible_ui.KIOSK_DISABLED_REQUESTS:
                child, approver = accessible_ui.KIOSK_DISABLED_REQUESTS[operation]
                result['request'].update(child=child, approver=approver)
            if operation == 'kiosk-no-child-form':
                result['request'].update(child='none', message='no-child')
            if operation == 'kiosk-no-approver-form':
                result['request'].update(approver='none', message='no-approver')
            if operation == 'overlay-request-form':
                result['request'].update(surface='child-overlay', child='fixture-child',
                    approver='other-fixture-parent', child_selector_enabled=False,
                    approver_selector_enabled=True, duration_enabled=True,
                    soft_choice_enabled=True, request_enabled=True, message='')
        if operation in accessible_ui.TOGGLE_OPERATIONS:
            result['toggle'] = accessible_ui.TOGGLE_OPERATIONS[operation]
        if operation in accessible_ui.MATCH_OPERATIONS:
            action = operation.removeprefix('match-')
            result['match'] = ({'closed': action} if action in ('save', 'cancel', 'reset') else
                {'invalid': action.removeprefix('invalid-'),
                 'message': accessible_ui.MATCH_INVALID[action.removeprefix('invalid-')]}
                if action.startswith('invalid-') else
                {'refusal': action} if action in ('wrong-app', 'ambiguous') else
                {'app': accessible_ui.MATCH_APP, 'rule': accessible_ui.MATCH_RULES[
                    1 if state['stage'] in ('saved-rule', 'independent-open', 'independent-read')
                    and plan is match_save_cancel.EDITOR_PLAN or state['stage'] == 'saved-rule' else 0]})
            if plan in (policy_qualification.PLAN, rejected_parent_rule.PLAN) and state['stage'] in plan.match_checks:
                expected = plan.match_checks[state['stage']]
                while expected not in accessible_ui.MATCH_RULES:
                    expected = plan.match_checks[expected]
                result['match'] = {'app': accessible_ui.MATCH_APP, 'rule': expected}
        if plan is rejected_parent_rule.PLAN and operation in (
                'parent-report-read', 'parent-report-actions', 'feedback-privacy-returned',
                'feedback-draft-reread'):
            result['feedback'] = {'draft': 'parent-rule-error' if operation == 'parent-report-read'
                else 'synthetic-first', 'attachments': ['diagnostic-logs.zip'],
                'collection': 'ready', 'validation': 'none', 'controls': 'ready'}
        if operation in accessible_ui.ACCESS_OPERATIONS:
            action = operation.removeprefix('access-')
            result['access'] = ({'app': accessible_ui.MATCH_APP,
                                 'choice': plan.access_checks[state['stage']]}
                if action == 'row' else {'page': 'screen'} if action == 'screen' else
                {'refusal': action} if action in ('wrong-row', 'disabled') else {'chosen': action})
        if plan in (fresh_thirty_allowance.PLAN, fresh_thirty_allowance.JORDAN_PLAN, policy_legend.PLAN, search_filters.PLAN) and state['stage'] in (
                'allowance-configured', 'balance-reread'):
            result['time_explanation'] = {
                'child': 'existing-fixture-child' if child == 'existing' else 'fixture-child',
                'daily': {'seconds': 1800, 'precision_seconds': 1},
                'one_time': {'seconds': 0, 'precision_seconds': 1},
                'total': {'seconds': 1800, 'precision_seconds': 1},
                'observed_monotonic_ns': len(boot_bindings)}
        if plan in (fresh_child_allowed.PLAN, fresh_child_denied.PLAN,
                    countdown_qualification.PLAN, countdown_qualification.OFF_PLAN,
                    shell_panel.PLAN, overlay_prompt.PLAN, overlay_approved_exit.PLAN) and state['stage'] == 'allowance-configured':
            seconds = 0 if plan is fresh_child_denied.PLAN else 900
            text = '15 minutes' if seconds else '0 seconds'
            result['time_explanation'] = {
                'child': 'fixture-child', 'expanded': True,
                'daily': {'text': text, 'seconds': seconds, 'precision_seconds': 1},
                'one_time': {'text': '0 seconds', 'seconds': 0, 'precision_seconds': 1},
                'total': {'text': text, 'seconds': seconds, 'precision_seconds': 1},
                'observed_monotonic_ns': len(boot_bindings)}
        if operation in accessible_ui.COUNTDOWN_OPERATIONS:
            present = operation == 'child-countdown-present'
            result['countdown'] = {'child': 'fixture-child', 'surface': 'desktop',
                'present': present, 'text': '00:14' if present else None,
                'observed_monotonic_ns': len(boot_bindings) * 1_000_000_000,
                'stable_ms': 0 if present else 2000}
        if operation in ('child-countdown-wrong-account-refused', 'overlay-wrong-account-refused'):
            result['refused'] = True
        if operation in ('gdm-child-time-denied', 'gdm-child-denied-return-ready'):
            result['denial'] = {'recipient': 'fixture-child', 'reason': 'time-limit',
                                'desktop_access': False}
        if operation in ('gdm-child-list', 'fresh-child-desktop'):
            shell = {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
            result['provider'] = {'shell': shell, 'gdm_version': '50.1'} if operation == 'gdm-child-list' else shell
        if operation in accessible_ui.FILTER_OPERATIONS:
            kind, mask, action = accessible_ui.FILTER_OPERATIONS[operation]
            options = accessible_ui.FILTER_OPTIONS[kind]
            result['filter'] = ({'opened' if action == 'open' else 'closed': kind}
                if action in ('open', 'closed') else
                {'filter': kind, 'selected': [option for index, option in enumerate(options)
                                            if mask & (1 << index)]} if action == 'read' else
                {'state': bool(mask & (1 << options.index(action))), 'activated': True})
        if operation in accessible_ui.PARENT_SAVE_OPERATIONS:
            result['save'] = accessible_ui.PARENT_SAVE_OPERATIONS[operation]
        if plan is native_fixture_qualification.PLAN and operation in (
                'existing-parent-app-rows', 'existing-parent-app-rows-reopened'):
            from native_fixtures import expected_rows
            result['apps'] = {'rows': [list(row) for row in expected_rows()]}
        if plan in (catalogue_search.PLAN, catalogue.PLAN, policy_legend.PLAN, search_filters.PLAN) and operation in accessible_ui.APP_ROW_OPERATIONS:
            from native_fixtures import expected_rows, search_rows
            if operation in accessible_ui.CATALOGUE_ROW_OPERATIONS:
                binding = accessible_ui.CATALOGUE_ROW_OPERATIONS[operation]
                rows = expected_rows() if binding == 'catalogue-clear' else search_rows(binding)
                result['apps'] = {'rows': [list(row) for row in rows]}
            elif operation.endswith(('wrong-child', 'wrong-page')):
                result['apps'] = {'refusal': 'wrong-child' if operation.endswith('wrong-child') else 'wrong-page'}
            elif operation == 'catalogue-incomplete-refused':
                result['apps'] = {'refusal': 'incomplete-result'}
            else:
                result['apps'] = {'rows': [list(row) for row in expected_rows()]}
        if plan is compose_observation.PLAN and operation in (
                'feedback-state-empty', 'feedback-trace-finish'):
            state_value = {'draft': 'initial-empty', 'attachments': ['diagnostic-logs.zip'],
                           'collection': 'ready', 'controls': 'ready',
                           'validation': 'none', 'send_enabled': True}
            if operation == 'feedback-state-empty':
                result['feedback_state'] = state_value
            else:
                result['samples'] = [{'elapsed_ms': 1, 'state': state_value}]
        if plan is kiosk_approved.PLAN:
            if operation == 'time-explanation-read':
                result['time_explanation'] = {'child': 'fixture-child',
                    'daily': {'seconds': 900, 'precision_seconds': 1},
                    'one_time': {'seconds': 0, 'precision_seconds': 1},
                    'total': {'seconds': 900, 'precision_seconds': 1},
                    'observed_monotonic_ns': 1_000_000_000}
            if operation.startswith('kiosk-valid-'):
                result['valid_choice'] = {'request': {'duration_seconds': 75},
                    'estimate': {'kind': 'fixed', 'seconds': 975},
                    'observed_monotonic_ns': 2_000_000_000}
            if operation == 'child-countdown-present':
                result['countdown'].update(text='00:16', observed_monotonic_ns=12_000_000_000)
        if plan is overlay_approved_exit.PLAN and operation == 'overlay-native-activity':
            result['activity'] = {'binding': 'native-primary', 'pid': 123,
                'endpoint': [':1.2', '/fixture'], 'state': {
                    'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft',
                    'score': 'Moves: 0; token: 0'}}
        if plan in (overlay_about.PLAN, overlay_prompt.PLAN, overlay_approved_exit.PLAN):
            if operation == 'time-explanation-setup-thirty-read':
                result['time_explanation'] = {'child': 'fixture-child',
                    'daily': {'seconds': 1800, 'precision_seconds': 1},
                    'one_time': {'seconds': 0, 'precision_seconds': 1},
                    'total': {'seconds': 1800, 'precision_seconds': 1},
                    'observed_monotonic_ns': 1_000_000_000}
            if operation in accessible_ui.OVERLAY_VALID_REQUESTS:
                seconds, custom, soft = accessible_ui.OVERLAY_VALID_REQUESTS[operation]
                result['valid_choice'] = {'request': {'surface': 'child-overlay',
                    'child': 'fixture-child', 'approver': 'fixture-parent',
                    'duration_seconds': seconds, 'custom_text': custom, 'allow_soft': soft},
                    'estimate': {'kind': 'fixed', 'seconds': (1800 if plan is overlay_about.PLAN else 900) + seconds},
                    'observed_monotonic_ns': 2_000_000_000}
        return result
    def accessibility_input(operation, terminal, mode='checked', *, worker_input=None, child=None):
        if worker_input is None:
            return observe_ui('accessibility-input-trace')
        token = 'a' * 32
        worker_input(token, 'c' * 64)
        proof = json.loads((directory / (state['stage'] + '.input.json')).read_bytes())
        assert proof['child'] == child == plan.child_bindings[state['stage']]
        (directory / (state['stage'] + '.input-done.json')).write_text(json.dumps(
            {'stage': state['stage'], 'token': token}))
        return {**observe_ui('parent-custom-save-trace'), 'token': token}

    def shell_success(worker_input):
        worker_input('a' * 32, 'a' * 64)
        proof = json.loads((directory / (state['stage'] + '.input.json')).read_bytes())
        assert proof['binding'] == 'overlay-approve' and proof['values'] == ['ret']
        (directory / (state['stage'] + '.input-done.json')).write_text(json.dumps(
            {'stage': state['stage'], 'token': 'a' * 32}))
        return observe_ui('overlay-approval-success')

    ui_observer = SimpleNamespace(
        observe_shell_success=shell_success, shell_approval_identity='a' * 64,
        boot_proof='b' * 64, observe=observe_ui,
        start_trace=lambda binding=None: {**observe_ui('feedback-trace-start'), 'token': 'a' * 32, 'ready': True},
        poll_trace=Mock(),
        observe_accessibility_input=accessibility_input,
        finish_trace=lambda token, terminal=None: {**observe_ui('feedback-trace-finish'), 'token': token},
        observe_challenge=lambda operation, binding: observe_ui(operation))
    monkeypatch.setattr(journeys, 'UiObservations', Mock(return_value=ui_observer))
    monkeypatch.setattr(command_documentation, 'observe',
                        lambda _transport, binding: {'operation': binding,
                                                       'outcome': 'passed',
                                                       'interface': 'SSH stdout'})
    monkeypatch.setattr(session_control, 'observe',
                        lambda _transport, binding: {'operation': binding,
                                                     'outcome': 'passed',
                                                     'interface': 'system session'})
    boundary = next(stage for stage, phase in plan.advance_after.items() if phase == 'step-2')
    state = {'stage': None, 'stored': False}
    context = SimpleNamespace(directory=directory, host_key='fixture-key', commands=Mock(),
        installed_snapshot='onpc-v9.8.7',
        guestfs=Mock(), credentials=Mock(), verified=SimpleNamespace(inputs=inputs),
        lease=SimpleNamespace(source=SimpleNamespace(uuid='fixture-uuid'),
            view=SimpleNamespace(domain_id=7), state={'run': 'a' * 32}, guard=Mock()))

    with PrivateCollector(run_id=contract.run_id, secrets=[], parent=tmp_path) as collector:
        recorder = ScenarioRecorder(contract, collector)
        recorder.begin_case(selector)
        save = collector.save_report

        def checkpoint(name, value):
            if state['stage'] == boundary:
                if (failure == 'observation-write' and value.get('event') == 'observation') or (
                        failure == 'return-step-write' and value.get('event') == 'step-started'
                        and value['active_step'] == 'step-2') or (
                        failure == 'assertion-write' and value.get('event') == 'assertion'):
                    raise OSError('fixed checkpoint failure')
            result = save(name, value)
            if value.get('event') == 'observation':
                assert not (directory / (state['stage'] + '.reply.json')).exists()
                state['stored'] = True
            return result

        monkeypatch.setattr(collector, 'save_report', checkpoint)
        acknowledged = []

        def worker(**options):
            assert options['authenticate'] is True
            assert options['guarded_observe'].__self__.review is False
            for stage in plan.stages:
                state.update(stage=stage, stored=False)
                request = directory / (stage + '.request.json')
                request.write_text(json.dumps({'stage': stage, 'screenshot': None}))

                def guard():
                    assert not (directory / (stage + '.reply.json')).exists()
                    if failure == 'worker-loss' and stage == boundary and state['stored']:
                        raise RuntimeError('fixed worker loss')
                    return 1800.0

                try:
                    options['guarded_observe'](guard)
                except (OSError, RuntimeError):
                    assert not (directory / (stage + '.reply.json')).exists()
                    with pytest.raises(EvidenceError, match='previous-failure'):
                        options['guarded_observe'](Mock())
                    raise
                assert state['stored']
                assert recorder._active['step_id'] == plan.advance_after.get(stage, plan.phases[stage])
                reply = json.loads((directory / (stage + '.reply.json')).read_bytes())
                if stage == 'ready':
                    expected_ready = {plan.worker_mode: True}
                    if plan.invocations:
                        expected_ready['invocations'] = list(plan.invocations)
                    if plan.challenges:
                        expected_ready['challenge_bindings'] = {
                            key: list(value) for key, value in plan.challenges.items()}
                    assert reply == expected_ready
                    provision.assert_not_called()
                else:
                    provision.assert_called_once()
                if plan is parent_access.PLAN and stage == 'app-grid':
                    assert reply == {'observed': stage}
                if plan is parent_access.PLAN and stage == 'system-prompt':
                    assert reply == {'observed': stage}
                tag = plan.screen_tags.get(stage, '')
                if tag.startswith('system:'):
                    assert reply == {'observed': stage}
                acknowledged.append(stage)
                if stage in plan.assertions_after:
                    assertion = recorder.records[0]['assertions'][-1]
                    assert assertion['assertion_id'] == plan.assertions_after[stage]
                    assert assertion['step_id'] == plan.phases[stage]
            assert [s['stage'] for s in options['validate']()] == list(plan.screen_tags)
            return dict(outcome='passed', shutdown_verified=True, worker_stopped=True, callback_closed=True)

        context.run_worker = worker
        actions = {name: Mock(return_value={'eligible_account_created': True})
                   for name in plan.stage_actions.values()}
        if plan is INTERVAL_RECORDER_PLAN:
            clock = [0.0]
            def sleep(seconds):
                clock[0] += seconds
            monkeypatch.setattr(real_interval, 'time', SimpleNamespace(
                monotonic=lambda: clock[0], sleep=sleep))
            actions = {'real-interval': real_interval.interval_action(5)}
        journey_type = (compose_observation.ComposeObservationJourney
                        if plan is compose_observation.PLAN else
                        fresh_child_allowed.FreshChildAllowedJourney
                        if plan is fresh_child_allowed.PLAN else
                        countdown_qualification.CountdownJourney
                        if plan in (countdown_qualification.PLAN, countdown_qualification.OFF_PLAN) else
                        shell_panel.ShellPanelJourney
                        if plan is shell_panel.PLAN else
                        fresh_child_denied.FreshChildDeniedJourney
                        if plan is fresh_child_denied.PLAN else
                        real_interval_qualification.RealIntervalJourney
                        if plan is INTERVAL_RECORDER_PLAN else
                        native_fixture_qualification.NativeFixtureJourney
                        if plan is native_fixture_qualification.PLAN else
                        native_app.NativeAppJourney
                        if plan is native_app.PLAN else
                        native_grid_usable.NativeGridJourney
                        if plan is native_grid_usable.PLAN else
                        catalogue_search.CatalogueSearchJourney
                        if plan is catalogue_search.PLAN else
                        catalogue.CatalogueJourney if plan is catalogue.PLAN else
                        policy_legend.PolicyLegendJourney if plan is policy_legend.PLAN else
                        rejected_parent_rule.ParentReportJourney if plan is rejected_parent_rule.PLAN else
                        MatchRuleJourney if plan in (match_save_cancel.PLAN, match_save_cancel.EDITOR_PLAN) else
                        access_choices.AccessChoiceJourney if plan in (access_choices.PLAN, policy_qualification.PLAN) else
                        search_filters.CataloguePolicyJourney if plan is search_filters.PLAN else
                        fresh_thirty_allowance.FreshThirtyAllowanceJourney
                        if plan in (fresh_thirty_allowance.PLAN, fresh_thirty_allowance.JORDAN_PLAN)
                        else overlay_prompt.OverlayPromptJourney if plan is overlay_prompt.PLAN
                        else overlay_approved_exit.OverlayApprovedExitJourney if plan is overlay_approved_exit.PLAN
                        else kiosk_approved.KioskRequestJourney if plan is kiosk_approved.PLAN
                        else journeys.InstalledJourney)
        if failure:
            with pytest.raises((OSError, RuntimeError)):
                if plan is overlay_about.PLAN:
                    overlay_about.execute(recorder, context)
                else:
                    journeys.record_installed_journey(recorder, context, plan, actions=actions,
                                                      journey_type=journey_type)
            assert acknowledged == list(plan.stages[:plan.stages.index(boundary)])
            assert recorder.records[0]['failures']
        else:
            if plan is overlay_about.PLAN:
                overlay_about.execute(recorder, context)
            else:
                journeys.record_installed_journey(recorder, context, plan, actions=actions,
                                                  journey_type=journey_type)
            assert acknowledged == list(plan.stages)
            steps = recorder.records[0]['steps']
            expected_steps = ['setup', 'start', 'step-1', 'step-2']
            if plan is parent_discovery.PLAN:
                expected_steps.append('step-3')
                actions['create-account'].assert_called_once()
            elif plan in (parent_discovery.EMPTY_PLAN, kiosk_no_child.CASE_PLAN):
                expected_steps.append('step-3')
                actions['prepare-empty'].assert_called_once()
            elif plan is kiosk_no_approver.CASE_PLAN:
                expected_steps.append('step-3')
                actions['prepare-no-approver'].assert_called_once()
            elif plan is kiosk_multiple.INELIGIBLE_CASE_PLAN:
                expected_steps.append('step-3')
                actions['prepare-ineligible-approver'].assert_called_once()
            elif plan in (command_help.PLAN, restricted_station.PLAN, kiosk_multiple.CASE_PLAN,
                          kiosk_about.PLAN, overlay_about.PLAN, parent_information.PLAN, search_filters.PLAN):
                expected_steps.append('step-3')
            assert [s['step_id'] for s in steps] == [*expected_steps, 'end']
            assert all(s['outcome'] == 'passed' for s in steps)
            if plan.assertions_after:
                assert [(a['assertion_id'], a['step_id']) for a in recorder.records[0]['assertions']] == [
                    (name, plan.phases[stage]) for stage, name in plan.assertions_after.items()]
                if plan is repeated_operations.PLAN:
                    assert operation_counts['parent-screen-page'] == 2
            else:
                assert steps[-2]['assertion_ids'] == ['visible-result']
        assert recorder._active is None
        setup.assert_not_called()
        journeys.Transport.return_value.reboot.assert_not_called()
        assert boot.read.call_count or boot_bindings
        assert all(call.args == ('boot',) for call in boot.read.call_args_list)


def test_repeated_assertion_write_failure_prevents_reply_and_latches(tmp_path, monkeypatch, journey_inventory):
    test_shared_plan_records_before_input_and_latches_transition_failures(
        tmp_path, monkeypatch, journey_inventory, repeated_operations.PLAN, 'assertion-write')


def test_challenge_assertion_write_failure_prevents_reply_and_latches(tmp_path, monkeypatch, journey_inventory):
    test_shared_plan_records_before_input_and_latches_transition_failures(
        tmp_path, monkeypatch, journey_inventory, challenges.PLAN, 'assertion-write')


def test_invalid_phase_plan_refuses_before_credentials_or_worker(tmp_path):
    context = SimpleNamespace(credentials=Mock(), run_worker=Mock())
    with pytest.raises(EvidenceError, match='phase-plan'):
        journeys.record_installed_journey(Mock(), context, replace(SYNTHETIC, phases={}))
    context.credentials.provision.assert_not_called()
    context.run_worker.assert_not_called()


@pytest.mark.parametrize('snapshot', [None, ''])
def test_missing_snapshot_refuses_without_installation_or_setup_reply(tmp_path, monkeypatch, snapshot):
    setup = Mock()
    transport = Mock()
    monkeypatch.setattr(installed_setup, 'InstalledSetup', setup)
    monkeypatch.setattr(journeys, 'Transport', transport)
    context = SimpleNamespace(directory=tmp_path, installed_snapshot=snapshot)
    journey = journeys.InstalledJourney(context, Mock(), SYNTHETIC)
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(
            json.dumps({'stage': stage, 'screenshot': None}))
    journey.step(Mock())
    with pytest.raises(EvidenceError, match='installed-snapshot-required'):
        journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(Mock())
    setup.assert_not_called()
    transport.assert_not_called()
    assert not (tmp_path / 'setup-detached.reply.json').exists()


@pytest.mark.parametrize('failure', [False, True])
def test_clean_baseline_qualification_installs_before_authorizing_customer_input(tmp_path, monkeypatch, failure):
    setup = Mock()
    setup.return_value.run.return_value = {'setup_reboot_verified': True, 'package_verified': False}
    if failure:
        setup.return_value.run.side_effect = EvidenceError('installation-failed')
    monkeypatch.setattr(installed_setup, 'InstalledSetup', setup)
    monkeypatch.setattr(journeys, 'Transport', Mock())
    monkeypatch.setattr(journeys, 'ReadOnlyObservations', Mock())
    monkeypatch.setattr(journeys.system, 'address', lambda *_args, **_kwargs: '192.0.2.1')
    context = SimpleNamespace(directory=tmp_path, install_current_package=True,
                              lease=Mock(), verified=Mock(), commands=Mock(), host_key='test-key')
    context.lease.state = {'run': 'test-run'}
    journey = journeys.InstalledJourney(context, Mock(), SYNTHETIC)
    guard = Mock()
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(
            json.dumps({'stage': stage, 'screenshot': None}))
    journey.step(guard)
    if failure:
        with pytest.raises(EvidenceError, match='installation-failed'):
            journey.step(guard)
        assert not (tmp_path / 'setup-detached.reply.json').exists()
    else:
        journey.step(guard)
        assert json.loads((tmp_path / 'setup-detached.reply.json').read_text()) == {'setup_complete': True}
    setup.return_value.run.assert_called_once_with(guard, verify=False)
    setup.return_value.provision.assert_not_called()


def test_review_requires_a_named_qualification_mode(tmp_path):
    with pytest.raises(EvidenceError, match='review-mode'):
        journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), SYNTHETIC, review=True)


def test_stage_action_runs_after_worker_guard_and_before_durable_reply(tmp_path, monkeypatch):
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock())
    plan = replace(SYNTHETIC, screen_tags={"created": "onpc-example-created"},
                   phases={"ready": "setup", "setup-detached": "setup", "created": "step-1"},
                   stage_actions={"created": "create-account"})
    directory = tmp_path
    for stage in plan.stages:
        (directory / (stage + ".request.json")).write_text(
            json.dumps({"stage": stage, "screenshot": None}))
    monkeypatch.setattr(journeys.system, "address", Mock(return_value="fixture-host"))
    transport = Mock()
    monkeypatch.setattr(journeys, "Transport", Mock(return_value=transport))
    monkeypatch.setattr(journeys, "ReadOnlyObservations", Mock(return_value=SimpleNamespace(
        read=Mock(return_value={"boot_sha256": "b" * 64}))))
    context = SimpleNamespace(directory=directory, host_key="fixture-key", commands=Mock(),
        installed_snapshot='onpc-v9.8.7',
        verified=Mock(), lease=SimpleNamespace(source=SimpleNamespace(uuid="fixture-uuid"),
        view=SimpleNamespace(domain_id=7), state={"run": "a" * 32}, guard=Mock()))
    events = []

    def action(journey, guard):
        assert journey.transport is transport
        assert not (directory / "created.reply.json").exists()
        guard()
        events.append("action")
        return {"eligible_account_created": True}

    journey = journeys.InstalledJourney(
        context, lambda stage, observed: events.append((stage, observed)), plan,
        actions={"create-account": action},
    )
    for _stage in plan.stages:
        journey.step(lambda: events.append("guard"))

    created = next(event[1] for event in events
                   if isinstance(event, tuple) and event[0] == "created")
    assert created["fixture"] == {"eligible_account_created": True}
    assert events.index("action") < events.index(("created", created))
    assert json.loads((directory / "created.reply.json").read_text()) == {"observed": "created"}


def test_stage_action_registry_refuses_missing_or_extra_actions(tmp_path):
    plan = replace(SYNTHETIC, stage_actions={"details": "create-account"})
    with pytest.raises(EvidenceError, match="stage-actions"):
        journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)


@pytest.mark.parametrize('fault', ['changed', 'missing', 'missing-earlier'])
def test_discovery_comparison_failure_blocks_fixture_and_reply(tmp_path, fault):
    plan = parent_discovery.PLAN
    action, progress = Mock(), Mock()
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), progress, plan,
                                        actions={'create-account': action})
    stage = 'fixture-requested'
    journey.steps = [{'stage': name} for name in plan.stages[:plan.stages.index(stage)]]
    earlier = journeys.SettingsObservation('existing-fixture-child', False, ('0 minutes',))
    if fault != 'missing-earlier': journey.settings_observations['parent-selected'] = earlier
    result = {'operation': 'discovery-ready', 'outcome': 'passed', 'interface': 'AT-SPI'}
    if fault != 'missing':
        result['settings'] = {'child': earlier.child, 'limit_enabled': fault == 'changed',
                              'allowance': ['0 minutes']}
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'a' * 64}))
    journey.ui = SimpleNamespace(boot_proof='a' * 64, observe=Mock(return_value=result))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    with pytest.raises(EvidenceError): journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    action.assert_not_called()
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('fault', ['child', 'toggle', 'allowance', 'missing', 'missing-earlier'])
def test_parent_information_return_comparison_refuses_before_durable_reply(tmp_path, fault):
    plan = parent_information.PLAN
    progress = Mock()
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    stage = 'parent-returned'
    journey.steps = [{'stage': name} for name in plan.stages[:plan.stages.index(stage)]]
    earlier = journeys.SettingsObservation('fixture-child', False, ('0 minutes',))
    if fault != 'missing-earlier':
        journey.settings_observations['parent-selected'] = earlier
    result = {'operation': 'parent-returned', 'outcome': 'passed', 'interface': 'AT-SPI'}
    if fault != 'missing':
        result['settings'] = {
            'child': 'existing-fixture-child' if fault == 'child' else earlier.child,
            'limit_enabled': fault == 'toggle',
            'allowance': ['1 hour'] if fault == 'allowance' else ['0 minutes'],
        }
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'a' * 64}))
    journey.ui = SimpleNamespace(boot_proof='a' * 64, observe=Mock(return_value=result))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    category = ('ui:missing-settings-observation' if fault in ('missing', 'missing-earlier')
                else 'ui:settings-changed:' + {'child': 'child', 'toggle': 'limit_enabled',
                                             'allowance': 'allowance'}[fault])
    with pytest.raises(EvidenceError, match=category):
        journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(Mock())
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('fault', [None, 'missing', 'reused', 'reordered', 'wrong-operation'])
@pytest.mark.parametrize('plan', [parent_discovery.PLAN, parent_discovery.EMPTY_PLAN, parent_access.PLAN,
                                 parent_about.PLAN, license_viewer_provider.PLAN,
                                 license_viewer_provider.WEBSITE_PLAN,
                                 license_viewer_provider.PRIVACY_PLAN,
                                 license_viewer_provider.SUPPORT_PLAN,
                                 license_viewer_provider.INFORMATION_PLAN,
                                 parent_information.PLAN,
                                 shell_search_results.PLAN, parent_search_launch.PLAN,
                                 shell_search.PLAN, kiosk_no_child.PLAN, kiosk_no_child.CASE_PLAN,
                                 kiosk_no_approver.PLAN, kiosk_no_approver.CASE_PLAN,
                                 restricted_station.PLAN],
                         ids=['discovery', 'empty', 'standard-access', 'about', 'license-viewer-provider',
                              'parent-website',
                              'parent-privacy',
                              'parent-support',
                              'parent-information',
                              'parent-links',
                              'shell-search', 'search-launch',
                              'standard-search', 'kiosk-no-child', 'no-child-case',
                              'kiosk-no-approver', 'no-parent-case', 'restricted-station'])
def test_consumers_require_all_fresh_ordered_semantic_results(tmp_path, monkeypatch, fault, plan):
    details, observations = [], []
    for stage, tag in plan.screen_tags.items():
        if tag.startswith('ui:'):
            observations.append({'stage': stage, 'ui': {
                'operation': tag[3:], 'outcome': 'passed', 'interface': 'AT-SPI'}})
        elif tag.startswith('system:'):
            observations.append({'stage': stage, 'system': {
                'operation': tag[7:], 'outcome': 'passed', 'interface': 'system session'}})
        else:
            details.append({'needle': tag, 'result': 'ok',
                            'area': [{'result': 'ok', 'similarity': 100}], 'screenshot': 'safe.png'})
        details.append({'title': plan.prefix + '-' + stage, 'result': 'ok'})
    if fault == 'missing': observations.pop()
    if fault == 'reused': observations[-1] = observations[-2]
    if fault == 'reordered': details[-1], details[-2] = details[-2], details[-1]
    if fault == 'wrong-operation': observations[-1]['ui']['operation'] = 'parent-selected'
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
    monkeypatch.setattr(journeys, 'screenshot', lambda *_: {'sha256': 'a' * 64})
    if fault:
        with pytest.raises(EvidenceError): journeys.matched_screens(tmp_path, plan, observations)
    else:
        assert len(journeys.matched_screens(tmp_path, plan, observations)) == len(plan.screen_tags)
