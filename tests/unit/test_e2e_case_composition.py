"""Inventory-driven composition checks: new ready cases cannot escape review.

Host-only: source reads, private Python values and mocked recorder entry points.
No VM, processes, shared files, sockets or displays; compatible unit scheduling.
"""

import ast
import importlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT


INVENTORY = json.loads((ROOT / 'tests/e2e/scenarios.json').read_text())
READY = [(scenario, variant) for scenario in INVENTORY['scenarios']
         for variant in scenario['variants'] if variant['status'] == 'ready']
CASE_MODULES = {Path(variant['executable']['path']).stem for _, variant in READY}
# Reviewed composition APIs, not a list of cases. Adding a ready inventory row
# is sufficient to exercise it. New mechanics belong behind a shared API.
APIS = {
    'account_fixture': {'DynamicAccountFixture', 'EmptyAccountFixture', 'station_fixture_actions'},
    'installed_journey': {'JourneyPlan', 'InstalledJourney', 'matched_screens', 'record_installed_journey'},
    'journey_blocks': {'fresh_desktop', 'parent_management', 'parent_search', 'observed_text',
                       'product_free_desktop', 'reboot_desktop', 'station_entry',
                       'custom_child_selection', 'custom_save_entry', 'ordinary_custom_save'},
    'journey_checks': {'allowed_app_rows', 'installed_accounts'},
    'request_flow': {'prepared_request'},
    'kiosk_approved_flow': {'approved_request', 'obtain_time'},
    'approval_flow': {'rejected_request'},
    'request_composition': {'KioskRequestJourney'},
    'package_install': {'check_install_result'},
    'package_journey': {'record_package_journey'},
    'ui_observations': {'SettingsObservation'},
    'feedback_composition': {'FeedbackValidationJourney', 'FeedbackDraftJourney', 'text_fragment',
                             'privacy_review'},
    'window_switch': {'window_switch_entry'},
    'feedback_formats': {'all_formats', 'format_stages'},
    'feedback_length': {'length_boundary'},
    'feedback_states': {'edit_states'},
    'feedback_rejection': {'STAGES'},
    'allowance_boundaries': {'BOUNDARY_SCREENS', 'boundary_screens'},
    'allowance_values': {'REPRESENTATIVE_PRESETS'},
    'file_chooser': {'stage_files', 'cleanup_files'},
    'synthetic_files': {'fixture_actions', 'read_declared_text', 'read_declared_zip',
                        'change_attachment_source'},
    'attachment_composition': {'file_handoff', 'boundary_batch', 'AttachmentJourney',
                               'chooser_preservation', 'attachment_removal'},
    'serial_harness': {'PLAN', 'SERIAL_STAGES', 'matched_screens', 'record_serial_journey',
                       'validate_completion', 'validate_stages'},
}
RECORDERS = ('record_installed_journey', 'record_package_journey', 'record_serial_journey')
# Review callable references as well as direct calls: passing an unreviewed
# class/action to a recorder must not hide case mechanics behind an import.
WORKER_APIS = {
    'onpc_progress': {'operation'},
    'testapi': {'record_info'},
    'onpc_harness': {'select_console'},
    'onpc_serial': {'attempt', 'login', 'command', 'logout', 'return_graphics'},
    'onpc_gdm': {'select_prompt', 'dismiss_product_free_prompt', 'reattach_functional',
                 'sign_in_challenge', 'enter_station'},
    'onpc_parent': {'login_functional', 'login_standard_functional', 'enter_desktop',
                    'sign_in', 'launch', 'select_child', 'open_for_child',
                    'open_from_app_grid', 'search_whole_query', 'launch_search_result',
                    'open_search', 'focus_search', 'enter_search_query', 'set_allowance'},
    'onpc_request_exit': {'enter_station', 'escape'},
    'onpc_window': {'close'},
    'onpc_about': {'open_about', 'open_license', 'return_to_parent'},
    'onpc_documentation': {'read'},
    'onpc_request_flow': {'prepare', 'reject', 'approve'},
    'onpc_station': {'restrictions'},
    'onpc_lifecycle': {'reopen'},
    'onpc_feedback_privacy': {'app_exit', 'preserve_dialog', 'review_privacy'},
    'onpc_allowance_boundaries': {'exercise', 'reload_child', 'select_child'},
    'onpc_text': {'replace_text', 'append_scalar', 'observed_custom_edits'},
    'onpc_format': {'apply_block', 'apply_bold', 'apply_inline', 'apply_all'},
    'onpc_feedback_states': {'rejection_observe', 'edit_states', 'length_boundary',
                             'input_hidden', 'input_complex', 'stable_trace', 'transition_trace',
                             'observed_toggle', 'custom_save_entry', 'run_save_order'},
    'onpc_feedback_read': {'activate_existing_window', 'prepare_window_switch',
                            'supply_files', 'boundary_batch', 'attachment_limits',
                            'chooser_preservation', 'attachment_removal'},
}


def composition_errors(source, case_modules, apis=APIS):
    """Review all definitions, including renamed callbacks and hidden helpers."""
    tree = ast.parse(source)
    allowed = {'dict', 'tuple', 'super'}
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                errors.append('unreviewed module import')
            modules = ([node.module or ''] if isinstance(node, ast.ImportFrom)
                       else [item.name for item in node.names])
            if (any(set(module.split('.')) & case_modules for module in modules)
                    or isinstance(node, ast.ImportFrom)
                    and any(item.name in case_modules for item in node.names)):
                errors.append('case dependency')
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if not node.level and item.name in apis.get(node.module, set()):
                        allowed.add(item.asname or item.name)
                    else:
                        errors.append('unreviewed import: ' + item.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(not isinstance(statement, (ast.Expr, ast.Assign, ast.Return))
                   for statement in node.body):
                errors.append('runtime mechanics in ' + node.name)
            for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
                if isinstance(call.func, ast.Attribute) and not (
                        call.func.attr == '__init__' and isinstance(call.func.value, ast.Call)
                        and isinstance(call.func.value.func, ast.Name)
                        and call.func.value.func.id == 'super'):
                    errors.append('runtime method call in ' + node.name)
        if isinstance(node, (ast.With, ast.AsyncWith, ast.Try, ast.While, ast.Lambda)):
            errors.append('case-owned runtime boundary')
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if isinstance(call.func, ast.Name):
            if call.func.id not in allowed:
                errors.append('unreviewed call: ' + call.func.id)
        elif isinstance(call.func, ast.Attribute):
            if call.func.attr not in ('items', 'update', '__init__'):
                errors.append('unreviewed method: ' + call.func.attr)
        else:
            errors.append('indirect call')
    return errors


@pytest.mark.parametrize('path', sorted({v['executable']['path'] for _, v in READY}))
def test_ready_modules_only_declare_and_compose_shared_apis(path):
    assert not composition_errors((ROOT / path).read_text(), CASE_MODULES)


def test_accessibility_trace_qualification_declares_shared_input_binding():
    assert not composition_errors(
        (ROOT / 'tests/e2e/accessibility_input_trace.py').read_text(), CASE_MODULES)
    assert not composition_errors(
        (ROOT / 'tests/e2e/parent_save_trace.py').read_text(), CASE_MODULES)
    assert not composition_errors(
        (ROOT / 'tests/e2e/feedback_collection.py').read_text(), CASE_MODULES)


@pytest.mark.parametrize('module', ['file_chooser', 'attachment_items', 'attachment_preview',
                                   'attachment_boundaries'])
def test_attachment_qualifications_keep_mechanics_in_shared_libraries(module):
    # Qualifications may extend another qualification's finite recipe. Ready
    # customer cases still cannot import these recipe-only APIs.
    apis = {**APIS, 'file_chooser': {*APIS['file_chooser'], 'SCREENS', 'journey'},
            'attachment_items': {'SCREENS'}, 'attachment_preview': {'PLAN'}}
    assert not composition_errors((ROOT / 'tests/e2e' / (module + '.py')).read_text(), CASE_MODULES, apis)


@pytest.mark.parametrize('source', [
    'def renamed_callback(r, c):\n    open("file")\n',
    'def helper(c):\n    c.transport.call([])\n',
    'from subprocess import run as harmless\nharmless([])\n',
    'from tests.e2e.future_case import PLAN as reused\n',
    'import tests.e2e.future_case as reused\n',
    'from tests.e2e import future_case as reused\n',
    'class CaseJourney:\n    def check(self, c):\n        if c: return c\n',
    'def helper(c):\n    with c.lease:\n        pass\n',
    'callback = lambda r, c: c.run_worker()\n',
    'from installed_journey import record_installed_journey\n'
    'from helper import Journey\nrecord_installed_journey(r, c, PLAN, journey_type=Journey)\n',
    'from helper import action\nACTIONS = {"fixture": action}\n',
    'from .installed_journey import record_installed_journey\n',
    'from kiosk_valid_duration import KioskValidDurationJourney\n',
    'from restricted_station_about import RestrictedStationAboutJourney\n',
    'from approval_flow import ApprovalFlowJourney\n',
])
def test_composition_guard_catches_new_cases_aliases_and_hidden_mechanics(source):
    assert composition_errors(source, {'future_case'})


def capture_composition(monkeypatch, variant):
    module = importlib.import_module(Path(variant['executable']['path']).stem)
    records = {}
    for name in RECORDERS:
        if hasattr(module, name):
            records[name] = Mock()
            monkeypatch.setattr(module, name, records[name])
    callback = module.E2E_CASES[variant['executable']['test_id']]
    callback(object(), SimpleNamespace())
    used = [(name, record) for name, record in records.items() if record.called]
    assert len(used) == 1
    name, record = used[0]
    assert record.call_count == 1
    plan = module.PLAN if name == 'record_serial_journey' else record.call_args.args[2]
    return name, plan, record.call_args.kwargs


@pytest.mark.parametrize('scenario,variant', READY, ids=[str(v['coverage_id']) for _, v in READY])
def test_ready_binding_phases_assertions_and_worker_are_registered(monkeypatch, scenario, variant):
    recorder, plan, options = capture_composition(monkeypatch, variant)
    if recorder != 'record_serial_journey':
        assert set(plan.phases) == set(plan.stages)
        steps = [step['id'] for phase in scenario['phases'].values() for step in phase]
        assert set(plan.phases.values()) <= set(steps)
        positions = [steps.index(plan.phases[stage]) for stage in plan.stages]
        assert positions == sorted(positions), 'recorder phase moves backwards'
        assert 'start' in plan.phases.values(), 'recorder start step is never opened'
        assert set(plan.advance_after) <= set(plan.screen_tags)
        for stage, following in plan.advance_after.items():
            index = plan.stages.index(stage)
            assert following == plan.phases[plan.stages[index + 1]]
        expected = {item['id']: item['step_id'] for item in scenario['assertions']['visible']}
        actual = ({name: plan.phases[stage] for stage, name in plan.assertions_after.items()}
                  if plan.assertions_after else {'visible-result': plan.phases[plan.stages[-1]]})
        assert actual == expected
        assert set(plan.stage_actions.values()) == (
            {'install-package'} if recorder == 'record_package_journey'
            else set(options.get('actions', {})))
    dispatch = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    branches = re.findall(r'if \(\$ready->\{(\w+)\}\) \{(.*?)\n    \}', dispatch, re.S)
    branch = [body for mode, body in branches if mode == plan.worker_mode]
    assert len(branch) == 1, plan.worker_mode
    workers = re.findall(r'\b(onpc_\w+)::(?:run|run_none)\(', branch[0])
    assert len(workers) == 1, plan.worker_mode
    source = (ROOT / 'tests/integration/graphical_smoke/lib' / (workers[0] + '.pm')).read_text()
    # Logging is harmless; raw input, process/file I/O and provider selection
    # belong to shared leaves, including the runner-smoke composition.
    assert not worker_errors(source)


@pytest.mark.parametrize('scenario,variant', [
    (s, v) for s, v in READY if v['coverage_id'] in (47, 48, 50, 51, 52, 192)
], ids=['47', '48', '50', '51', '52', '192'])
def test_ready_requests_use_shared_comparisons_with_declared_endpoints(monkeypatch, scenario, variant):
    from request_composition import KioskRequestJourney
    _, plan, options = capture_composition(monkeypatch, variant)
    assert options['journey_type'] is KioskRequestJourney
    expected = ({'flow-preserved': ('flow-before', 'approval-flow:changed-form', 'preserved_choices')}
                if variant['coverage_id'] in (51, 52) else
                {'form-returned': ('open-estimate', 'kiosk-about:changed-form', 'unchanged_form')}
                if variant['coverage_id'] == 192 else {})
    assert plan.request_checks == expected
    assert plan.balance_checks == ({'allowance-configured': 1800}
                                   if variant['coverage_id'] == 192 else {})


def worker_errors(source):
    # Strip ordinary literal labels/comments, not code: a stage such as
    # 'child-choices-open' must not be mistaken for Perl's file-open operator.
    code = re.sub(r''''(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|\#.*''', '', source)
    return (bool(re.search(r'\b(?:open|sysread|syswrite|system|exec|qx|readpipe)\b', code))
            or bool(re.search(r'\b(?:send_key|type_string|mouse_set|mouse_click|assert_screen|check_screen)\b', code))
            or bool(set(re.findall(r'testapi::(\w+)', code)) - {'record_info'})
            or any(name not in WORKER_APIS.get(module, set())
                   for module, name in re.findall(r'\b(\w+)::(\w+)\s*\(', code))
            or bool(set(re.findall(r'->\s*(\w+)\s*\(', code)) - {
                'new', 'seen', 'consume_observation', 'finish',
                'declare_invocations', 'declare_challenges'})
            or any(owner != 'onpc_journey'
                   for owner in re.findall(r'\b(\w+)->new\s*\(', code))
            or '`' in source)


@pytest.mark.parametrize('source', [
    "open my $file, '<', 'input';", "system('command');", 'testapi::send_key("ret");',
    'send_key "ret";', 'my $output = `command`;', 'my $output = qx(command);',
    'case_local_helper::act($journey);', 'onpc_parent::unreviewed_input($journey);',
    '$journey->unreviewed_input();', 'CaseMechanics->new();',
])
def test_worker_guard_rejects_bare_and_qualified_io(source):
    assert worker_errors(source)


def test_worker_guard_allows_semantic_labels_and_logging():
    assert not worker_errors("$journey->seen('child-choices-open'); # open result\n"
                             "testapi::record_info('stage', 'read result');")


def test_entry_fragments_do_not_share_mutable_recipe_state():
    from journey_blocks import (fresh_desktop, parent_management, parent_search,
                                product_free_desktop, reboot_desktop, station_entry, observed_text)
    for factory, args in ((fresh_desktop, ('parent',)), (fresh_desktop, ('other-child',)),
                          (parent_search, ()), (parent_management, ()),
                          (product_free_desktop, ()), (reboot_desktop, ()),
                          (station_entry, ('cancel-',)), (observed_text, ('renamed', 'body-clear'))):
        expected = factory(*args)
        changed = factory(*args)
        changed.clear()
        assert factory(*args) == expected


def test_routine_login_has_no_wrong_account_visit_or_prompt_dismissal():
    from journey_blocks import fresh_desktop
    for role in ('parent', 'other-child'):
        stages = fresh_desktop(role)
        assert not any('wrong' in value or 'other-parent' in value or 'dismiss' in value
                       for value in (*stages, *stages.values()))
        assert len(stages) == 5
