"""Owned account input, exact eligibility, and independent result guards."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import CHILD, EXISTING_CHILD, PARENT, UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import WORKER, accounts_form
from ui_observations import RequestObservation, UiObservations


@pytest.mark.parametrize('field', ['child', 'approver'])
def test_selection_checks_exact_choices_and_reads_independent_enabled_result(field):
    ui, selector, choices, expected = accounts_form(field)
    operation = f'kiosk-{field}-select'
    result = ui.run(operation, '')
    observed = RequestObservation.from_request(result['request'], operation=operation)
    assert observed.child == 'fixture-child'
    assert observed.request_enabled
    selector.setValue.assert_called_once_with(str(ui.fixture_uids[expected[0]]))
    selector.getChoices.assert_called()
    selector.action.do_action.assert_not_called()
    choices.children[0].action.do_action.assert_not_called()
    choices.children[1].action.do_action.assert_not_called()
    with pytest.raises(FrozenInstanceError):
        observed.child = 'changed'


@pytest.mark.parametrize('fault', [None, 'wrong-selection', 'wrong-description',
                                 'malformed-selection', 'wrong-owner', 'missing-result', 'save-failed'])
def test_child_selection_confirms_account_before_first_run_language_input(fault):
    ui, selector, choices, expected = accounts_form()
    ui.timeout = .5  # The full form is reread after successful language setup.
    window = ui.find_id('kiosk-request-window')
    ready = ui.find_id('kiosk-language-ready')
    button = Node(identity='language-continue')
    dialog = Node(identity='language-dialog', children=[button])
    dialog.parent = window
    commit = selector.setValue.side_effect

    def select(index):
        commit(index)
        window.children.remove(ready)
        window.children.append(dialog)
        # The language modal disables the underlying request controls.
        selector.states.discard('sensitive')
        if fault == 'wrong-selection':
            selector.value = '1002'
        elif fault == 'wrong-description':
            selector.description = f'Selected account: {EXISTING_CHILD}.'
        elif fault == 'malformed-selection':
            selector.value = ['1001', '1002']
        elif fault == 'wrong-owner':
            ui.owner_pids = lambda: {999}
        elif fault == 'missing-result':
            selector.value = ''
        return True

    def save(_):
        # The action has already passed its pre-input latch guard and is now
        # latched until the independent language completion read.
        assert ui.input_uncertain
        assert selector.getValue() == '1001'
        assert selector.description == f'Selected account: {CHILD}.'
        if fault != 'save-failed':
            window.children.remove(dialog)
            window.children.append(ready)
            selector.states.add('sensitive')
        return True

    selector.setValue.side_effect = select
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
    selector.setValue.assert_called_once_with('1001')
    selector.action.do_action.assert_not_called()
    choices.children[0].action.do_action.assert_not_called()


@pytest.mark.parametrize('field', ['child', 'approver'])
@pytest.mark.parametrize('fault', [None, 'save-failed', 'still-disabled'])
def test_account_input_completes_startup_language_before_setting_selector(
        field, fault):
    ui, selector, choices, expected = accounts_form(field)
    window = ui.find_id('kiosk-request-window')
    ready = ui.find_id('kiosk-language-ready')
    button = Node(identity='language-continue')
    dialog = Node(identity='language-dialog', children=[button])
    dialog.parent = window
    window.children.remove(ready)
    window.children.append(dialog)
    selector.states.discard('sensitive')
    events = []

    def save(_):
        events.append('save')
        selector.setValue.assert_not_called()
        selector.action.do_action.assert_not_called()
        for choice in choices.children:
            choice.action.do_action.assert_not_called()
        if fault != 'save-failed':
            window.children.remove(dialog)
            window.children.append(ready)
            if fault != 'still-disabled':
                selector.states.add('sensitive')
        return True

    commit = selector.setValue.side_effect

    def select(value):
        events.append('select')
        assert dialog not in window.children and ready in window.children
        assert ui.input_uncertain
        return commit(value)

    button.action.do_action.side_effect = save
    selector.setValue.side_effect = select
    if fault:
        with pytest.raises(UiError, match=('timeout:language-saved' if fault == 'save-failed'
                                          else 'kiosk-account-unavailable')):
            ui.select_kiosk_account(field, expected[0], expected=expected)
        assert events == ['save']
        if fault == 'save-failed':
            assert ui.input_uncertain
            with pytest.raises(UiError, match='uncertain-input'):
                ui.select_kiosk_account(field, expected[0], expected=expected)
        selector.action.do_action.assert_not_called()
        selector.setValue.assert_not_called()
        for choice in choices.children:
            choice.action.do_action.assert_not_called()
    else:
        result = ui.select_kiosk_account(field, expected[0], expected=expected)
        assert events == ['save', 'select'] and not ui.input_uncertain
        selector.setValue.assert_called_once_with(str(ui.fixture_uids[expected[0]]))
        selector.action.do_action.assert_not_called()
        choices.children[0].action.do_action.assert_not_called()
        choices.children[1].action.do_action.assert_not_called()
        assert result['request_enabled']
    button.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'noncanonical',
                                 'disabled', 'hidden', 'wrong-owner', 'wrong-surface'])
def test_bad_offered_set_never_commits(fault):
    ui, selector, choices, expected = accounts_form()
    if fault == 'missing':
        selector.choices.pop()
    elif fault == 'extra':
        selector.choices.append('9999')
    elif fault == 'duplicate':
        selector.choices.append(selector.choices[0])
    elif fault == 'noncanonical':
        selector.choices[0] = 1001
    elif fault in ('disabled', 'hidden'):
        selector.states.discard('sensitive' if fault == 'disabled' else 'visible')
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    else:
        ui.find_id('kiosk-request-window').identity = 'parent-window'
    with pytest.raises(UiError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.setValue.assert_not_called()


def test_wrong_or_absent_choice_refuses_before_any_input():
    ui, selector, choices, expected = accounts_form()
    for name in (PARENT, 'Missing account'):
        with pytest.raises(UiError, match='kiosk-account-choice'):
            ui.select_kiosk_account('child', name, expected=expected)
    selector.action.do_action.assert_not_called()
    selector.setValue.assert_not_called()


def test_overlay_disabled_child_selector_refuses_input():
    ui, selector, choices, expected = accounts_form()
    selector.states.discard('sensitive')
    with pytest.raises(UiError, match='kiosk-account-unavailable'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.action.do_action.assert_not_called()
    selector.setValue.assert_not_called()


def test_uncertain_action_is_never_replayed():
    ui, selector, choices, expected = accounts_form()
    selector.setValue.side_effect = RuntimeError('lost reply')
    with pytest.raises(RuntimeError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    with pytest.raises(UiError, match='uncertain-input'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.setValue.assert_called_once_with('1001')
    selector.action.do_action.assert_not_called()


def test_successful_input_without_changed_selection_fails():
    ui, selector, choices, expected = accounts_form()
    commit = selector.setValue.side_effect
    def wrong(index):
        commit(index)
        selector.value = '1002'
        selector.description = f'Selected account: {EXISTING_CHILD}.'
        return True
    selector.setValue.side_effect = wrong
    with pytest.raises(UiError, match='timeout:kiosk-selected-account'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.setValue.assert_called_once_with('1001')
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
    from tools.test_storage import named_input
    assert check.ASSETS == named_input(vm_source=True, fixture_source=True)


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
    selector.choices.append('1010')
    with pytest.raises(UiError, match='eligible-set'):
        ui.select_kiosk_account('approver', PARENT, expected=expected)
    for choice in choices.children:
        choice.action.do_action.assert_not_called()
    selector.setValue.assert_not_called()


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
    selector.setValue.assert_not_called()


def test_account_snapshot_uses_one_complete_read_for_input_boundary():
    ui, selector, choices, expected = accounts_form()
    ui.nodes = Mock(wraps=ui.nodes)
    assert ui.kiosk_account_snapshot('child')[0] is selector
    assert ui.nodes.call_count == 1


@pytest.mark.parametrize('fault', ['query', 'stale', 'owner', 'present'])
@pytest.mark.parametrize('persistent', [False, True])
def test_parent_wrong_entry_requires_complete_refusal(monkeypatch, fault, persistent):
    import accessible_ui as adapter

    window = Node(identity='parent-window')
    ui = ui_for(window)
    now = [0.0]
    ui.timeout = .4
    ui.query_errors = (LookupError,)
    monkeypatch.setattr(adapter, 'time', SimpleNamespace(
        monotonic=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds)))
    original = ui.kiosk_account_snapshot
    reads = []

    def snapshot(field):
        reads.append(ui._observation_generation)
        if persistent or len(reads) == 1:
            if fault == 'query':
                raise LookupError('service-missing')
            if fault == 'stale':
                raise UiError('ui:stale-request-form')
            if fault == 'owner':
                raise UiError('ui:wrong-owner')
            return object()  # A present form must never qualify wrong entry.
        return original(field)

    ui.kiosk_account_snapshot = snapshot
    if fault in ('owner', 'present') or persistent:
        with pytest.raises(UiError, match={
                'query': 'timeout', 'stale': 'stale-request-form',
                'owner': 'wrong-owner', 'present': 'wrong-entry-accepted'}[fault]):
            ui.run('parent-kiosk-refused', '')
    else:
        assert ui.run('parent-kiosk-refused', '')['outcome'] == 'passed'
    if fault in ('query', 'stale'):
        assert len(reads) >= 2 and len(set(reads)) == len(reads)
        assert now[0] == (.4 if persistent else .2)
    else:
        assert len(reads) == 1 and now[0] == 0
    window.action.do_action.assert_not_called()
    assert not ui.input_uncertain


@pytest.mark.parametrize('field', ['child', 'approver'])
@pytest.mark.parametrize('boundary', ['initial', 'offered', 'selected'])
@pytest.mark.parametrize('persistent', [False, True], ids=['transient', 'persistent'])
def test_account_selection_discards_stale_reads_without_replaying_input(
        monkeypatch, field, boundary, persistent):
    import accessible_ui as adapter

    ui, selector, choices, expected = accounts_form(field)
    root = ui.root()
    stale = Node('private stale content', states=('defunct',))
    stale.parent = root
    now = [0.0]
    ui.timeout = .4
    monkeypatch.setattr(adapter, 'time', SimpleNamespace(
        monotonic=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds)))
    original_nodes = ui.nodes
    stale_reads = []

    def nodes(*args, **kwargs):
        if stale in root.children:
            stale_reads.append(selector.setValue.call_count)
            if len(stale_reads) > 1 and not persistent:
                root.children.remove(stale)
        yield from original_nodes(*args, **kwargs)

    monkeypatch.setattr(ui, 'nodes', nodes)
    if boundary == 'initial':
        root.children.append(stale)
    elif boundary == 'offered':
        def offered():
            stale_reads.append(selector.setValue.call_count)
            if persistent or len(stale_reads) == 1:
                raise UiError('ui:stale-request-form')
            return list(selector.choices)

        selector.getChoices.side_effect = offered
    else:
        original_input = selector.setValue.side_effect

        def enter(index):
            original_input(index)
            root.children.append(stale)
            return True

        selector.setValue.side_effect = enter

    if persistent:
        with pytest.raises(UiError, match='stale-request-form'):
            ui.select_kiosk_account(field, expected[0], expected=expected)
        assert now[0] == ui.timeout
    else:
        result = ui.select_kiosk_account(field, expected[0], expected=expected)
        assert RequestObservation.from_request(result, operation=f'kiosk-{field}-select').request_enabled
        assert stale not in root.children and not ui.input_uncertain
    assert len(stale_reads) >= 2
    assert set(stale_reads) == {int(boundary == 'selected')}
    assert selector.setValue.call_count == (not persistent or boundary == 'selected')
    selector.action.do_action.assert_not_called()
    choices.children[0].action.do_action.assert_not_called()
    choices.children[1].action.do_action.assert_not_called()


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
