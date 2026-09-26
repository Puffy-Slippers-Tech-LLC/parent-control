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
    'journey_blocks': {'fresh_desktop', 'parent_management', 'parent_search',
                       'product_free_desktop', 'reboot_desktop', 'station_entry'},
    'journey_checks': {'allowed_app_rows', 'installed_accounts'},
    'request_flow': {'prepared_request'},
    'kiosk_approved_flow': {'approved_request', 'obtain_time'},
    'kiosk_valid_duration': {'KioskValidDurationJourney'},
    'package_install': {'check_install_result'},
    'package_journey': {'record_package_journey'},
    'ui_observations': {'SettingsObservation'},
    'serial_harness': {'record_serial_journey'},
}
RECORDERS = ('record_installed_journey', 'record_package_journey', 'record_serial_journey')


def composition_errors(source, case_modules):
    """Review all definitions, including renamed callbacks and hidden helpers."""
    tree = ast.parse(source)
    allowed = {'dict', 'tuple', 'super'}
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = ([node.module or ''] if isinstance(node, ast.ImportFrom)
                       else [item.name for item in node.names])
            if (any(set(module.split('.')) & case_modules for module in modules)
                    or isinstance(node, ast.ImportFrom)
                    and any(item.name in case_modules for item in node.names)):
                errors.append('case dependency')
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if item.name in APIS.get(node.module, set()):
                        allowed.add(item.asname or item.name)
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


def worker_errors(source):
    # Strip ordinary literal labels/comments, not code: a stage such as
    # 'child-choices-open' must not be mistaken for Perl's file-open operator.
    code = re.sub(r''''(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|\#.*''', '', source)
    return (bool(re.search(r'\b(?:open|sysread|syswrite|system|exec|qx|readpipe)\b', code))
            or bool(re.search(r'\b(?:send_key|type_string|mouse_set|mouse_click|assert_screen|check_screen)\b', code))
            or bool(set(re.findall(r'testapi::(\w+)', code)) - {'record_info'})
            or '`' in source)


@pytest.mark.parametrize('source', [
    "open my $file, '<', 'input';", "system('command');", 'testapi::send_key("ret");',
    'send_key "ret";', 'my $output = `command`;', 'my $output = qx(command);',
])
def test_worker_guard_rejects_bare_and_qualified_io(source):
    assert worker_errors(source)


def test_worker_guard_allows_semantic_labels_and_logging():
    assert not worker_errors("$journey->seen('child-choices-open'); # open result\n"
                             "testapi::record_info('stage', 'read result');")


def test_entry_fragments_do_not_share_mutable_recipe_state():
    from journey_blocks import (fresh_desktop, parent_management, parent_search,
                                product_free_desktop, reboot_desktop, station_entry)
    for factory, args in ((fresh_desktop, ('parent',)), (fresh_desktop, ('other-child',)),
                          (parent_search, ()), (parent_management, ()),
                          (product_free_desktop, ()), (reboot_desktop, ()),
                          (station_entry, ('cancel-',))):
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
