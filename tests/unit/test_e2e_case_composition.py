"""Inventory-driven composition checks: new ready cases cannot escape review.

Host-only: source reads, private Python values and mocked recorder entry points.
No VM, processes, shared files, sockets or displays; compatible unit scheduling.
"""

import importlib
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT
from tests.support.e2e_composition import APIS, CASE_MODULES, READY, composition_errors


RECORDERS = ('record_installed_journey', 'record_package_journey', 'record_serial_journey',
             'record_lifecycle_journey')
# Review callable references as well as direct calls: passing an unreviewed
# class/action to a recorder must not hide case mechanics behind an import.
WORKER_APIS = {
    'onpc_app_rows': {'native_entry', 'search', 'filter', 'read_rows', 'legend', 'edit_policy',
                      'match_editor', 'match_response', 'match_edit', 'access_choice',
                      'native_search', 'native_launch_grid', 'native_open_grid',
                      'native_open_command', 'native_use_app', 'native_close_app',
                      'native_usable_app', 'native_read_activity', 'native_finish_app',
                      'native_activity_entry', 'native_activity_resume'},
    'onpc_progress': {'operation'},
    'testapi': {'record_info'},
    'onpc_harness': {'select_console'},
    'onpc_serial': {'attempt', 'login', 'command', 'logout', 'return_graphics'},
    'onpc_gdm': {'select_prompt', 'dismiss_product_free_prompt', 'reattach_functional',
                 'sign_in_challenge', 'named_login', 'enter_station', 'return_from_time_denial'},
    'onpc_parent': {'login_functional', 'login_standard_functional', 'enter_desktop',
                    'sign_in', 'launch', 'select_child', 'open_for_child',
                    'open_from_app_grid', 'search_whole_query', 'launch_search_result',
                    'open_search', 'focus_search', 'enter_search_query', 'set_allowance', 'language_selection',
                    'named_management', 'language_presentation_roundtrip', 'language_save',
                    'dialog_visit', 'dialog_close', 'dialog_use'},
    'onpc_request_exit': {'enter_station', 'escape'},
    'onpc_desktop_session': {'switch_user', 'lock', 'observe_lock', 'enter_desktop'},
    'onpc_window': {'close'},
    'onpc_about': {'open_about', 'read_help', 'open_from_help', 'open_license', 'close_information',
                   'check_link', 'return_to_parent', 'overlay_license'},
    'onpc_documentation': {'read'},
    'onpc_request_flow': {'prepare', 'reject', 'approve', 'obtain_time', 'overlay_entry', 'overlay_to_kiosk', 'kiosk_to_overlay', 'prepare_transfer_allowances', 'daily_station_entry', 'shell_cancel', 'shell_approve', 'shell_reject', 'overlay_approve', 'overlay_reject', 'prepare_chinese', 'approve_chinese'},
    'onpc_station': {'restrictions'},
    'onpc_lifecycle': {'reopen'},
    'onpc_customer_reboot': {'chinese_desktop_renewal', 'chinese_initial_notice', 'chinese_initial_form',
                            'chinese_current_entry', 'restart_reentry', 'restart_roundtrip', 'restart_kiosk_usability', 'restart_request_usability', 'restart_notice', 'run_parent_notice', 'run_child_notice', 'run_kiosk_notice'},
    'onpc_feedback_privacy': {'app_exit', 'preserve_dialog', 'review_privacy', 'review_parent_report',
                              'close_parent_report'},
    'onpc_allowance_boundaries': {'exercise', 'reload_child', 'select_child', 'custom_value'},
    'onpc_allowance_selection': {'select'},
    'onpc_text': {'replace_text', 'append_scalar', 'observed_custom_edits'},
    'onpc_format': {'apply_block', 'apply_bold', 'apply_inline', 'apply_all'},
    'onpc_feedback_states': {'rejection_observe', 'edit_states', 'length_boundary',
                             'input_hidden', 'input_complex', 'stable_trace', 'transition_trace',
                             'observed_toggle', 'custom_save_entry', 'run_save_order'},
    'onpc_feedback_read': {'activate_existing_window', 'prepare_window_switch',
                            'supply_files', 'boundary_batch', 'attachment_limits',
                            'chooser_preservation', 'attachment_removal',
                            'save_handoff', 'save_cancellation', 'diagnostic_export'},
}


@pytest.mark.parametrize('path', sorted({v['executable']['path'] for _, v in READY}))
def test_ready_modules_only_declare_and_compose_shared_apis(path):
    assert not composition_errors((ROOT / path).read_text(), CASE_MODULES)


def test_overlay_valid_choices_only_composes_shared_apis():
    assert not composition_errors((ROOT / 'tests/e2e/overlay_valid_choices.py').read_text(), CASE_MODULES)
    assert not composition_errors((ROOT / 'tests/e2e/overlay_choices.py').read_text(), CASE_MODULES)
    assert not composition_errors((ROOT / 'tests/e2e/choices_overlay_to_kiosk.py').read_text(), CASE_MODULES)
    assert not composition_errors((ROOT / 'tests/e2e/cross_surface.py').read_text(), CASE_MODULES)
    assert not composition_errors((ROOT / 'tests/e2e/overlay_prompt.py').read_text(), CASE_MODULES)
    assert not composition_errors((ROOT / 'tests/e2e/overlay_approved_exit.py').read_text(), CASE_MODULES)
    assert not composition_errors((ROOT / 'tests/e2e/overlay_rejection.py').read_text(), CASE_MODULES)
    assert not composition_errors((ROOT / 'tests/e2e/overlay_license.py').read_text(), CASE_MODULES)


def test_retained_qualifiers_share_comparisons_without_recipe_inheritance():
    import ast
    from retained_parent import RetainedParentJourney
    from retained_entry import RetainedEntryJourney
    from journey_checks import RetainedDesktopJourney
    assert RetainedParentJourney.__bases__ == RetainedEntryJourney.__bases__ == (RetainedDesktopJourney,)
    for module in ('retained_parent', 'retained_entry'):
        tree = ast.parse((ROOT / 'tests/e2e' / (module + '.py')).read_text())
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        assert len(classes) == 1
        assert [node.name for node in classes[0].body if isinstance(node, ast.FunctionDef)] == ['__init__']
        assert all(node.module not in ('retained_parent', 'retained_entry')
                   for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
        assert any(node.module == 'journey_blocks' and
                   'retained_parent_entry' in {item.name for item in node.names}
                   for node in tree.body if isinstance(node, ast.ImportFrom))


def test_accessibility_trace_qualification_declares_shared_input_binding():
    assert not composition_errors(
        (ROOT / 'tests/e2e/accessibility_input_trace.py').read_text(), CASE_MODULES)
    assert not composition_errors(
        (ROOT / 'tests/e2e/parent_save_trace.py').read_text(), CASE_MODULES)
    assert not composition_errors(
        (ROOT / 'tests/e2e/feedback_collection.py').read_text(), CASE_MODULES)
    assert not composition_errors(
        (ROOT / 'tests/e2e/save_chooser.py').read_text(), CASE_MODULES)


def test_match_qualification_declares_shared_operations_and_comparisons():
    assert not composition_errors(
        (ROOT / 'tests/e2e/match_save_cancel.py').read_text(), CASE_MODULES)
    assert not composition_errors(
        (ROOT / 'tests/e2e/rejected_parent_rule.py').read_text(), CASE_MODULES)


def test_fresh_child_denial_fragments_support_independent_named_invocations():
    from journey_blocks import fresh_desktop, rejected_gdm_return
    from private_artifacts import EvidenceError
    first = {f'independent-{stage}': operation for stage, operation in
             fresh_desktop('child', 'time-denied').items()}
    second = {f'return-{stage}': operation for stage, operation in rejected_gdm_return().items()}
    assert list(first.values()) == ['ui:gdm-child-list', 'ui:gdm-child-focused',
        'ui:gdm-child-recipient', 'ui:gdm-child-recipient-rechecked', 'ui:gdm-child-time-denied']
    assert list(second.values()) == ['ui:gdm-child-denied-return-ready',
        'ui:gdm-child-denied-return-state', 'ui:gdm-child-denied-returned']
    first.clear()
    assert fresh_desktop('child', 'time-denied')['denied'] == 'ui:gdm-child-time-denied'
    for binding in (('parent', 'time-denied'), ('other-child', 'time-denied'), ('child', 'anything')):
        with pytest.raises(EvidenceError): fresh_desktop(*binding)


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
    'from save_chooser import save_handoff\n',
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
        declared_actions = set(options.get('actions', {}))
        if recorder == 'record_lifecycle_journey':
            declared_actions.update('package-' + binding for _, binding, _ in options['operations'])
        assert set(plan.stage_actions.values()) == (
            {'install-package'} if recorder == 'record_package_journey'
            else declared_actions)
    dispatch = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    branches = re.findall(r'if \(\$ready->\{(\w+)\}\) \{(.*?)\n    \}', dispatch, re.S)
    branch = [body for mode, body in branches if mode == plan.worker_mode]
    assert len(branch) == 1, plan.worker_mode
    workers = re.findall(r'\b(onpc_\w+)::(?:run|run_reverse|run_none|run_links|run_overlay|run_removal|run_parent_notice|run_child_notice|run_kiosk_notice|search_filters|parent_error_report)\(', branch[0])
    assert len(workers) == 1, plan.worker_mode
    source = (ROOT / 'tests/integration/graphical_smoke/lib' / (workers[0] + '.pm')).read_text()
    # Logging is harmless; raw input, process/file I/O and provider selection
    # belong to shared leaves, including the runner-smoke composition.
    assert not worker_errors(source)


@pytest.mark.parametrize('scenario,variant', [
    (s, v) for s, v in READY if v['coverage_id'] in (47, 48, 50, 51, 52, 191, 192)
], ids=['47', '48', '50', '51', '52', '191', '192'])
def test_ready_requests_use_shared_comparisons_with_declared_endpoints(monkeypatch, scenario, variant):
    from request_composition import KioskRequestJourney
    _, plan, options = capture_composition(monkeypatch, variant)
    assert options['journey_type'] is KioskRequestJourney
    expected = ({'flow-preserved': ('flow-before', 'approval-flow:changed-form', 'preserved_choices')}
                if variant['coverage_id'] in (51, 52) else
                {'form-returned': ('open-estimate', 'kiosk-about:changed-form', 'unchanged_form')}
                if variant['coverage_id'] == 192 else
                {'form-returned': ('captured-form', 'overlay-about:changed-form', 'unchanged_form')}
                if variant['coverage_id'] == 191 else {})
    assert plan.request_checks == expected
    assert plan.balance_checks == ({'allowance-configured': 1800}
                                   if variant['coverage_id'] in (191, 192) else {})


@pytest.mark.parametrize('case,children', [(58, ('jordan', 'riley')), (59, ('riley', 'jordan'))])
def test_remembered_choices_case_compares_both_children_without_retained_logins(monkeypatch, case, children):
    import accessible_ui
    from request_composition import KioskRequestJourney
    variant = next(variant for _, variant in READY if variant['coverage_id'] == case)
    _, plan, options = capture_composition(monkeypatch, variant)
    assert options['journey_type'] is KioskRequestJourney
    assert plan.request_transfer_checks == {
        **{child + '-transfer-read': child + '-source' for child in ('jordan', 'riley')},
        **{child + '-revisit-read': child + '-source' for child in ('jordan', 'riley')},
    }
    assert [stage for stage in plan.screen_tags if stage.endswith('-source')] == [
        child + '-source' for child in children]
    assert [stage for stage in plan.screen_tags if stage.endswith('-revisit-read')] == [
        child + '-revisit-read' for child in children]
    assert set(plan.challenges) == {'initial', 'jordan-entry', 'riley-entry'}
    assert not any('return-entry' in stage for stage in plan.screen_tags)
    assert not any(tag.endswith('-entry-retained') for tag in plan.screen_tags.values())
    binding = 'remembered' if case == 58 else 'remembered-second'
    for child, values in zip(children, ((75, '1.25', True), (150, '2.5', False))):
        for surface, approver in (('overlay', accessible_ui.OTHER_PARENT), ('kiosk', accessible_ui.PARENT)):
            assert accessible_ui.TRANSFER_REQUESTS[f'{binding}-{surface}-{child}-read'] == (*values, approver)
    assert plan.balance_checks == {'riley-allowance': 1800, 'jordan-allowance': 1800}
    assert plan.assertions_after == {children[-1] + '-revisit-read': 'visible-result'}
    assert plan.advance_after == {'installed-greeter': 'step-1', children[0] + '-source': 'step-2',
                                  children[0] + '-transfer-read': 'step-3'}


def test_reverse_remembered_case_compares_transfer_and_reopened_overlays(monkeypatch):
    import accessible_ui
    from request_composition import KioskRequestJourney
    variant = next(variant for _, variant in READY if variant['coverage_id'] == 60)
    _, plan, options = capture_composition(monkeypatch, variant)
    assert options['journey_type'] is KioskRequestJourney
    assert plan.request_transfer_checks == {
        **{child + '-transfer-read': child + '-source' for child in ('jordan', 'riley')},
        **{child + '-revisit-read': child + '-source' for child in ('jordan', 'riley')},
    }
    assert [stage for stage in plan.screen_tags if stage.endswith('-source')] == ['jordan-source', 'riley-source']
    assert [stage for stage in plan.screen_tags if stage.endswith('-revisit-read')] == [
        'jordan-revisit-read', 'riley-revisit-read']
    for child, values in (('jordan', (75, '1.25', True)), ('riley', (150, '2.5', False))):
        for surface, approver in (('overlay', accessible_ui.OTHER_PARENT), ('kiosk', accessible_ui.PARENT)):
            assert accessible_ui.TRANSFER_REQUESTS[f'remembered-{surface}-{child}-read'] == (*values, approver)
        for prefix in (child + '-seed', child, child + '-revisit'):
            assert any(stage == prefix + '-logout' for stage in plan.screen_tags) == (
                prefix != 'riley-revisit')
    assert set(plan.challenges) == {'initial', *(
        child + '-' + suffix + '-entry' for child in ('jordan', 'riley')
        for suffix in ('seed', 'transfer', 'revisit'))}
    assert not any(tag.endswith('-entry-retained') for tag in plan.screen_tags.values())
    assert not any('approval' in tag for tag in plan.screen_tags.values())
    assert plan.balance_checks == {'riley-allowance': 1800, 'jordan-allowance': 1800}
    assert plan.assertions_after == {'riley-revisit-read': 'visible-result'}
    assert plan.advance_after == {'installed-greeter': 'step-1', 'jordan-source': 'step-2',
                                  'jordan-transfer-read': 'step-3'}


def test_ready_catalogue_case_uses_the_shared_engine_with_recipe_endpoints(monkeypatch):
    from native_fixtures import CataloguePolicyJourney
    variant = next(variant for _, variant in READY if variant['coverage_id'] == 184)
    _, plan, options = capture_composition(monkeypatch, variant)
    assert options['journey_type'] is CataloguePolicyJourney
    assert plan.catalogue_checks == {
        'initial-rows': 'initial', 'name-rows': ('catalogue-name', 3, 7),
                      'filtered-rows': ('catalogue-name', 2, 1), 'cleared-rows': 'unchanged'}


def test_kiosk_approved_case_requires_immediate_exit_then_fresh_child_countdown(monkeypatch):
    from request_composition import KioskRequestJourney
    variant = next(variant for _, variant in READY if variant['coverage_id'] == 49)
    _, plan, options = capture_composition(monkeypatch, variant)
    assert options['journey_type'] is KioskRequestJourney
    assert plan.balance_checks == {'time-explanation-read': 900}
    assert plan.countdown_checks == {'countdown': ('open-estimate', 975, 1, 180)}
    assert plan.screen_tags['approval-success'] == 'ui:kiosk-mate-submit-immediate'
    assert list(plan.screen_tags)[-7:] == ['new-returned', 'fresh-installed-greeter',
        'fresh-child-focused', 'fresh-child-recipient-qualified',
        'fresh-child-recipient-rechecked', 'fresh-desktop', 'countdown']
    assert plan.challenges == {'child-login': ('child', 'fresh-child-recipient-qualified',
                                             'fresh-child-recipient-rechecked')}


def test_ready_parent_report_case_uses_shared_review_close_and_exact_restoration(monkeypatch):
    from parent_reports import ParentReportJourney, report_review, report_close
    from match_rules import MATCH_RULES
    variant = next(variant for _, variant in READY if variant['coverage_id'] == 205)
    _, plan, options = capture_composition(monkeypatch, variant)
    assert options['journey_type'] is ParentReportJourney
    assert plan.match_checks['confirmed-rule'] == MATCH_RULES[1]
    assert all(plan.match_checks[stage] == 'confirmed-rule' for stage in ('restored-rule', 'final-rule'))
    assert all(plan.screen_tags[stage] == tag for stage, tag in report_review('review').items())
    assert all(plan.screen_tags[stage] == tag for stage, tag in report_close('decline').items())
    assert plan.advance_after == {'rejected-save': 'step-2', 'restored-rule': 'step-3'}


def worker_errors(source):
    # Strip ordinary literal labels/comments, not code: a stage such as
    # 'child-choices-open' must not be mistaken for Perl's file-open operator.
    code = re.sub(r''''(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|\#.*''', '', source)
    code = re.sub(r'\bqw\s*\([^)]*\)', '', code)
    return (bool(re.search(r'\b(?:open|sysread|syswrite|system|exec|qx|readpipe)\b', code))
            or bool(re.search(r'\b(?:send_key|type_string|mouse_set|mouse_click|assert_screen|check_screen)\b', code))
            or bool(set(re.findall(r'testapi::(\w+)', code)) - {'record_info'})
            or any(name not in WORKER_APIS.get(module, set())
                   for module, name in re.findall(r'\b(\w+)::(\w+)\s*\(', code))
            or bool(set(re.findall(r'->\s*(\w+)\s*\(', code)) - {
                'new', 'seen', 'consume_observation', 'finish',
                'declare_invocations', 'declare_challenges', 'scope'})
            or any(owner != 'onpc_journey'
                   for owner in re.findall(r'\b(\w+)->new\s*\(', code))
            or bool(re.search(r'\bexchange\s*=>\s*sub\b', code))
            or '`' in source)


@pytest.mark.parametrize('source', [
    "open my $file, '<', 'input';", "system('command');", 'testapi::send_key("ret");',
    'send_key "ret";', 'my $output = `command`;', 'my $output = qx(command);',
    'case_local_helper::act($journey);', 'onpc_parent::unreviewed_input($journey);',
    '$journey->unreviewed_input();', 'CaseMechanics->new();',
    "onpc_journey->new(exchange => sub { $exchange->('activity-' . $_[0], $_[1]) });",
])
def test_worker_guard_rejects_bare_and_qualified_io(source):
    assert worker_errors(source)


def test_worker_guard_allows_semantic_labels_and_logging():
    assert not worker_errors("$journey->seen('child-choices-open'); # open result\n"
                             "testapi::record_info('stage', 'read result');\n"
                             "$journey->seen($_) for qw(open-cancel open-returned);")
    assert worker_errors("my @labels = qw(open-cancel); open my $file, '<', 'input';")


def test_entry_fragments_do_not_share_mutable_recipe_state():
    from journey_blocks import (fresh_desktop, parent_management, parent_reopen, parent_search,
                                product_free_desktop, package_installation, reboot_desktop, station_entry, observed_text)
    for factory, args in ((fresh_desktop, ('parent',)), (fresh_desktop, ('other-child',)),
                          (fresh_desktop, ('child',)),
                          (parent_search, ()), (parent_management, ()), (parent_reopen, ()),
                          (product_free_desktop, ()), (package_installation, ()), (reboot_desktop, ()),
                          (station_entry, ('cancel-',)), (observed_text, ('renamed', 'body-clear'))):
        expected = factory(*args)
        changed = factory(*args)
        changed.clear()
        assert factory(*args) == expected


def test_install_fragment_preserves_customer_and_qualification_boundaries():
    from clean_install import PLAN as customer
    from package_install import PLAN as qualification
    from package_upgrade import PLAN as upgrade
    from chinese_kiosk_lifecycle import PLAN as chinese
    from journey_blocks import package_installation

    # Independent public operation/order oracle; a wrong-entry refusal is a
    # qualification assertion, never an extra customer step or implicit reboot.
    expected = [
        ('installed-greeter', 'ui:gdm-product-free-list'),
        ('parent-focused', 'ui:gdm-product-free-focused'),
        ('recipient-qualified', 'ui:gdm-parent-recipient'),
        ('recipient-rechecked', 'ui:gdm-parent-recipient-rechecked'),
        ('desktop', 'ui:fresh-parent-desktop'),
        ('command-context', 'system:parent-command-context'),
        ('package-submitted', 'system:parent-command-context'),
        ('package-result', 'system:parent-command-context'),
    ]
    assert list(package_installation().items()) == expected
    assert list(customer.screen_tags.items())[:len(expected)] == expected
    for plan in (qualification, upgrade, chinese):
        assert list(plan.screen_tags.items())[:len(expected) + 1] == [
            ('wrong-entry', 'ui:gdm-product-free-list'), *expected]
    assert customer.stage_actions == {'package-submitted': 'install-package'}
    assert qualification.stage_actions['wrong-entry'] == 'refuse-command'
    assert upgrade.stage_actions['package-submitted'] == chinese.stage_actions['package-submitted'] == 'install-previous'
    assert customer.phases['package-result'] == 'step-1'
    assert qualification.phases['package-result'] == 'step-2'


def test_current_chinese_binding_has_setup_before_one_install_and_one_reboot():
    from chinese_current_install import PLAN
    from journey_blocks import product_free_desktop
    assert list(PLAN.screen_tags.items())[:7] == [
        ('wrong-entry', 'ui:gdm-product-free-list'), *product_free_desktop().items()]
    stages = list(PLAN.screen_tags)
    assert stages.index('language-desktop') < stages.index('package-submitted')
    assert stages.index('package-result') < stages.index('initial-notice') < stages.index('reboot-requested')
    assert stages.index('reboot-greeter') < stages.index('initial-language') < stages.index('initial-form')
    assert PLAN.reboot_transitions == (('reboot-requested', 'reboot-greeter'),)
    assert PLAN.stage_actions['package-submitted'] == 'install-package'
    assert PLAN.screen_tags['language-installed-greeter'] == 'ui:gdm-product-free-standard-list'
    assert PLAN.screen_tags['language-standard-focused'] == 'ui:gdm-product-free-standard-focused'
    assert PLAN.screen_tags['install-installed-greeter'] == 'ui:gdm-product-free-list'
    assert PLAN.screen_tags['install-parent-focused'] == 'ui:gdm-product-free-focused'
    assert PLAN.screen_tags['return-installed-greeter'] == 'ui:gdm-list'
    assert not any('upgrade' in value or 'approval' in value or 'language-save' in value
                   for value in (*PLAN.stage_actions.values(), *PLAN.screen_tags.values()))


def test_routine_login_has_no_wrong_account_visit_or_prompt_dismissal():
    from journey_blocks import fresh_desktop
    for role in ('parent', 'other-child', 'child'):
        stages = fresh_desktop(role)
        assert not any('wrong' in value or 'other-parent' in value or 'dismiss' in value
                       for value in (*stages, *stages.values()))
        assert len(stages) == 5


def test_product_free_desktop_binding_refuses_invalid_roles_and_result():
    from journey_blocks import fresh_desktop
    from private_artifacts import EvidenceError
    stages = fresh_desktop('child', product_free=True)
    assert list(stages.values()) == ['ui:gdm-product-free-child-list',
        'ui:gdm-product-free-child-focused', 'ui:gdm-child-recipient',
        'ui:gdm-child-recipient-rechecked', 'ui:fresh-child-desktop']
    for role, expected, binding in (('child', 'time-denied', True), ('parent', 'time-denied', True),
                                    ('other-child', 'success', 'true')):
        with pytest.raises(EvidenceError):
            fresh_desktop(role, expected, product_free=binding)
