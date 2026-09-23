"""Keep ready recipes declarative and shared input mechanics outside cases."""

import ast
import re

from tests.support.paths import ROOT


CASES = ('controller_qualification', 'parent_discovery', 'parent_access',
         'parent_terminal', 'parent_about', 'command_help')
WORKERS = ('onpc_parent_discovery', 'onpc_parent_access', 'onpc_parent_terminal',
           'onpc_parent_about', 'onpc_command_help')


def test_ready_case_callbacks_only_compose_shared_envelopes_and_fixtures():
    for name in CASES:
        tree = ast.parse((ROOT / 'tests/e2e' / (name + '.py')).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in CASES, (name, node.module)
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith('execute'):
                continue
            # Scenario callbacks select a plan and bind fixture actions. Runtime
            # branching, direct I/O, recording and recovery belong to the harness.
            assert all(isinstance(stmt, (ast.Expr, ast.Assign)) for stmt in node.body), name
            calls = [item for item in ast.walk(node) if isinstance(item, ast.Call)]
            assert all(isinstance(call.func, ast.Name) and call.func.id in {
                'record_serial_journey', 'record_installed_journey',
                'DynamicAccountFixture', 'EmptyAccountFixture',
            } for call in calls), name


def test_ready_worker_recipes_delegate_input_and_observations():
    for name in WORKERS:
        source = (ROOT / 'tests/integration/graphical_smoke/lib' / (name + '.pm')).read_text()
        assert 'testapi' not in source, name
        assert not re.search(r'\b(?:open|sysread|syswrite|system|exec)\s*\(', source), name
        assert set(re.findall(r'^sub (\w+)', source, re.MULTILINE)) <= {'run', 'run_none'}, name


def test_entry_fragments_do_not_share_mutable_recipe_state():
    from journey_blocks import fresh_desktop, parent_search
    for factory, args in ((fresh_desktop, ('parent',)),
                          (fresh_desktop, ('other-child',)), (parent_search, ())):
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
