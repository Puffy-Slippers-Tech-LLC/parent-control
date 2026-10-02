"""Owned account input, exact eligibility, and independent result guards."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import CHILD, EXISTING_CHILD, PARENT, UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node
from tests.support.e2e_kiosk import WORKER, accounts_form
from ui_observations import RequestObservation, UiObservations


@pytest.mark.parametrize('field', ['child', 'approver'])
@pytest.mark.parametrize('fault', [None, 'unchanged', 'selection', 'extra'])
def test_multiple_inspect_collapse_and_decode_without_selection(field, fault):
    import json
    ui, selector, choices, _ = accounts_form(field)
    form = ui.find_id('kiosk-request-form')
    child = ui.find_id('kiosk-child-selector')
    child.children[0].identity = 'kiosk-child-selected-1002'
    child.description = f'Selected account: {EXISTING_CHILD}.'
    for node in form.children:
        if node.identity == 'kiosk-screen-limit-notice':
            node.states.discard('showing')
        else:
            node.states.add('sensitive')
    def toggle(_):
        if 'showing' in choices.states:
            if fault != 'unchanged':
                choices.states.discard('showing')
            if fault == 'selection':
                child.children[0].identity = 'kiosk-child-selected-1001'
                child.description = f'Selected account: {CHILD}.'
        else:
            choices.states.add('showing')
        return True
    selector.action.do_action.side_effect = toggle
    if fault == 'extra':
        choices.children.append(Node(identity=f'kiosk-{field}-choice-9999'))
        with pytest.raises(UiError, match='eligible-set'):
            ui.run(f'multiple-{field}-open', '')
        return
    ui.run(f'multiple-{field}-open', '')
    operation = f'multiple-{field}-closed'
    if fault == 'unchanged':
        with pytest.raises(UiError, match='timeout'):
            ui.run(operation, '')
        with pytest.raises(UiError, match='uncertain-input'):
            ui.run(operation, '')
    else:
        result = ui.run(operation, '')
        observer = UiObservations(Mock())
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        if fault == 'selection':
            with pytest.raises(EvidenceError, match='ui:request'):
                observer.observe(operation)
        else:
            assert observer.observe(operation) == result
    assert selector.action.do_action.call_count == 2
    for choice in choices.children:
        choice.action.do_action.assert_not_called()


@pytest.mark.parametrize('field', ['child', 'approver'])
def test_selection_checks_exact_choices_and_reads_independent_enabled_result(field):
    ui, selector, choices, expected = accounts_form(field)
    operation = f'kiosk-{field}-select'
    result = ui.run(operation, '')
    observed = RequestObservation.from_request(result['request'], operation=operation)
    assert observed.child == 'fixture-child'
    assert observed.request_enabled
    selector.action.do_action.assert_called_once()
    choices.children[0].action.do_action.assert_called_once()
    choices.children[1].action.do_action.assert_not_called()
    with pytest.raises(FrozenInstanceError):
        observed.child = 'changed'


@pytest.mark.parametrize('fault', [None, 'wrong-selection', 'wrong-description',
                                 'duplicate', 'wrong-owner', 'missing-result', 'save-failed'])
def test_child_selection_confirms_account_before_first_run_language_input(fault):
    ui, selector, choices, expected = accounts_form()
    ui.timeout = .5  # The full form is reread after successful language setup.
    window = ui.find_id('kiosk-request-window')
    ready = ui.find_id('kiosk-language-ready')
    button = Node(identity='language-continue')
    dialog = Node(identity='language-dialog', children=[button])
    dialog.parent = window
    commit = choices.children[0].action.do_action.side_effect

    def select(index):
        commit(index)
        window.children.remove(ready)
        window.children.append(dialog)
        # The language modal disables the underlying request controls.
        selector.states.discard('sensitive')
        if fault == 'wrong-selection':
            selector.children[0].identity = 'kiosk-child-selected-1002'
        elif fault == 'wrong-description':
            selector.description = f'Selected account: {EXISTING_CHILD}.'
        elif fault == 'duplicate':
            duplicate = Node(identity=selector.children[0].identity)
            duplicate.parent = selector
            selector.children.append(duplicate)
        elif fault == 'wrong-owner':
            ui.owner_pids = lambda: {999}
        elif fault == 'missing-result':
            selector.children.clear()
        return True

    def save(_):
        # The action has already passed its pre-input latch guard and is now
        # latched until the independent language completion read.
        assert ui.input_uncertain
        assert selector.children[0].identity == 'kiosk-child-selected-1001'
        assert selector.description == f'Selected account: {CHILD}.'
        if fault != 'save-failed':
            window.children.remove(dialog)
            window.children.append(ready)
            selector.states.add('sensitive')
        return True

    choices.children[0].action.do_action.side_effect = select
    button.action.do_action.side_effect = save
    if fault:
        with pytest.raises(UiError):
            ui.select_kiosk_account('child', CHILD, expected=expected)
        assert ui.input_uncertain
        with pytest.raises(UiError, match='uncertain-input'):
            ui.select_kiosk_account('child', CHILD, expected=expected)
    else:
        result = ui.select_kiosk_account('child', CHILD, expected=expected)
        assert result['child'] == 'fixture-child' and result['request_enabled']
        assert not ui.input_uncertain
    assert button.action.do_action.call_count == (1 if fault in (None, 'save-failed') else 0)
    selector.action.do_action.assert_called_once()
    choices.children[0].action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'wrong-label',
                                 'disabled', 'hidden', 'wrong-owner', 'wrong-surface'])
def test_bad_offered_set_never_commits(fault):
    ui, selector, choices, expected = accounts_form()
    target = choices.children[0]
    if fault == 'missing':
        choices.children.pop()
    elif fault == 'extra':
        choices.children.append(Node(identity='kiosk-child-choice-9999'))
    elif fault == 'duplicate':
        choices.children.append(Node(identity=target.identity))
    elif fault == 'wrong-label':
        target.name = 'Child account: wrong'
    elif fault in ('disabled', 'hidden'):
        target.states.discard('sensitive' if fault == 'disabled' else 'visible')
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    else:
        ui.find_id('kiosk-request-window').identity = 'parent-window'
    with pytest.raises(UiError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    target.action.do_action.assert_not_called()


def test_wrong_or_absent_choice_refuses_before_any_input():
    ui, selector, choices, expected = accounts_form()
    for name in (PARENT, 'Missing account'):
        with pytest.raises(UiError, match='kiosk-account-choice'):
            ui.select_kiosk_account('child', name, expected=expected)
    selector.action.do_action.assert_not_called()


def test_overlay_disabled_child_selector_refuses_input():
    ui, selector, choices, expected = accounts_form()
    selector.states.discard('sensitive')
    with pytest.raises(UiError, match='kiosk-account-unavailable'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.action.do_action.assert_not_called()


def test_uncertain_action_is_never_replayed():
    ui, selector, choices, expected = accounts_form()
    choices.children[0].action.do_action.side_effect = RuntimeError('lost reply')
    with pytest.raises(RuntimeError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    with pytest.raises(UiError, match='uncertain-input'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.action.do_action.assert_called_once()
    choices.children[0].action.do_action.assert_called_once()


def test_successful_input_without_changed_selection_fails():
    ui, selector, choices, expected = accounts_form()
    commit = choices.children[0].action.do_action.side_effect
    def wrong(index):
        commit(index)
        selector.children[0].identity = 'kiosk-child-selected-1002'
        selector.description = f'Selected account: {EXISTING_CHILD}.'
        return True
    choices.children[0].action.do_action.side_effect = wrong
    with pytest.raises(UiError, match='timeout:kiosk-request-form'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    choices.children[0].action.do_action.assert_called_once()
    with pytest.raises(UiError, match='uncertain-input'):
        ui.select_kiosk_account('child', CHILD, expected=expected)


def test_controller_validates_enabled_results_and_rejects_wrong_account():
    import json
    ui, *_ = accounts_form('approver')
    result = ui.run('kiosk-approver-select', '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe('kiosk-approver-select') == result
    result['request']['approver'] = 'other-fixture-parent'
    observer.call.return_value = (json.dumps(result).encode(), [])
    with pytest.raises(EvidenceError, match='ui:request'):
        observer.observe('kiosk-approver-select')


def test_qualification_uses_shared_snapshot_and_guarded_envelope(tmp_path):
    import check_e2e_kiosk_eligible_choices as check
    from parent_setup_qualification import KioskEligibleChoicesQualification, KioskEntryQualification
    from kiosk_eligible_choices import PLAN
    context = SimpleNamespace(directory=tmp_path)
    journey = KioskEligibleChoicesQualification.journey(context, Mock())
    assert journey.plan is PLAN
    import json
    from tests.support.paths import ROOT
    version = json.loads((ROOT / 'data/app.json').read_bytes())['version']
    assert context.installed_snapshot == 'onpc-v' + version
    assert KioskEligibleChoicesQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert check.ASSETS == Path(__file__).resolve().parents[2] / 'output/test-runs/host/allocations/onpc-parent-setup-input'


def test_ineligible_profile_reuses_all_pairs_and_owned_fixture(tmp_path):
    from kiosk_multiple import PLAN, INELIGIBLE_PLAN
    from parent_setup_qualification import KioskIneligibleQualification, KioskEntryQualification
    context = SimpleNamespace(directory=tmp_path)
    journey = KioskIneligibleQualification.journey(context, Mock())
    assert journey.plan is INELIGIBLE_PLAN
    assert INELIGIBLE_PLAN.screen_tags == PLAN.screen_tags
    assert INELIGIBLE_PLAN.worker_mode == PLAN.worker_mode
    assert INELIGIBLE_PLAN.stage_actions == {'setup-detached': 'prepare-ineligible-approver'}
    assert set(journey.actions) == {'prepare-ineligible-approver'}
    assert KioskIneligibleQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot


@pytest.mark.parametrize('conflict', ['kiosk_multiple', 'parent_toggle', 'mate_prompt'])
def test_ineligible_profile_refuses_conflicting_modes(conflict):
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='prerequisites'):
        smoke.main(assets='/unused', provision_credentials=True, kiosk_ineligible=True,
                   **{conflict: True})


def test_locked_administrator_cannot_appear_in_exact_public_choices():
    ui, selector, choices, expected = accounts_form('approver')
    choices.children.append(Node(identity='kiosk-approver-choice-1010',
                                 name='Approver account: Locked Parent'))
    with pytest.raises(UiError, match='eligible-set'):
        ui.select_kiosk_account('approver', PARENT, expected=expected)
    for choice in choices.children:
        choice.action.do_action.assert_not_called()


def test_ineligible_case_binds_fresh_fixture_to_complete_recorder(monkeypatch):
    import kiosk_multiple
    context, recorder = Mock(), Mock()
    actions = {'prepare-ineligible-approver': Mock()}
    fixture = Mock(return_value=actions)
    record = Mock()
    monkeypatch.setattr(kiosk_multiple, 'station_fixture_actions', fixture)
    monkeypatch.setattr(kiosk_multiple, 'record_installed_journey', record)
    kiosk_multiple.E2E_CASES['ineligible-parent'](recorder, context)
    fixture.assert_called_once_with(context, 'ineligible-approver')
    record.assert_called_once_with(recorder, context, kiosk_multiple.INELIGIBLE_CASE_PLAN,
                                   timeout=1800, actions=actions)
    assert kiosk_multiple.INELIGIBLE_CASE_PLAN.stage_actions == {
        'setup-detached': 'prepare-ineligible-approver'}


@pytest.mark.parametrize('conflict', ['parent_toggle', 'kiosk_entry', 'license_viewer_provider'])
def test_qualification_refuses_conflicting_modes_before_vm_access(conflict):
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='kiosk-eligible-choices-prerequisites'):
        smoke.main(assets='/unused', provision_credentials=True,
                   kiosk_eligible_choices=True, **{conflict: True})


def test_account_snapshot_rejects_incomplete_tree_before_input():
    ui, selector, choices, expected = accounts_form()
    choices.children.append(None)
    with pytest.raises(UiError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.action.do_action.assert_not_called()


def test_account_snapshot_uses_one_complete_read_for_input_boundary():
    ui, selector, choices, expected = accounts_form()
    ui.nodes = Mock(wraps=ui.nodes)
    assert ui.kiosk_account_snapshot('child')[0] is selector
    assert ui.nodes.call_count == 1


@pytest.mark.parametrize('refusal', [None, 'save-enabled', 'child-selected'])
def test_worker_order_stops_on_failed_public_result(monkeypatch, refusal):
    import json
    from tests.support.perl import run_perl
    from kiosk_eligible_choices import PLAN
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    if refusal:
        assert not result['ok']
        assert stages == expected[:expected.index(refusal) + 1]
    else:
        assert result['ok'], result['error']
        assert stages == expected
        assert result['events'][-1] == ['power', 'off']
