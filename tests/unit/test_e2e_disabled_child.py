"""Case 57 preserves disabled policy and gates every input on public results."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import UiError
from disabled_child import PLAN
from installed_journey import InstalledJourney
from private_artifacts import EvidenceError
from test_e2e_request_choices import disabled_accounts_form
from test_e2e_kiosk_eligible_choices import WORKER
from tests.support.perl import run_perl
from ui_observations import RequestObservation, UiObservations


def test_inspect_collapse_and_selection_do_not_activate_disabled_controls():
    ui, selector, choices, _ = disabled_accounts_form()
    def toggle(_):
        if 'showing' in choices.states:
            choices.states.discard('showing')
        else:
            choices.states.add('showing')
        return True
    selector.action.do_action.side_effect = toggle
    ui.run('kiosk-child-choices-open', '')
    for node in choices.children:
        node.action.do_action.assert_not_called()
    closed = ui.run('kiosk-child-choices-closed', '')
    before = RequestObservation.from_request(
        closed['request'], operation='kiosk-child-choices-closed')
    assert before.child == 'existing-fixture-child'
    assert not before.approver_selector_enabled and not before.request_enabled
    ui.run('kiosk-disabled-child-select', '')
    after = ui.run('kiosk-disabled-form', '')
    assert RequestObservation.from_request(
        after['request'], operation='kiosk-disabled-form').child == 'fixture-child'
    assert selector.action.do_action.call_count == 3
    for identity in ('kiosk-approver-selector', 'kiosk-request-submit'):
        ui.find_id(identity).action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['hidden', 'wrong-owner', 'prompt', 'extra-choice'])
def test_inspection_refuses_unsafe_list(fault):
    ui, selector, choices, _ = disabled_accounts_form()
    if fault == 'hidden':
        choices.children[0].states.discard('visible')
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    elif fault == 'prompt':
        ui.system_prompt_kind = Mock(return_value='polkit')
    elif fault == 'extra-choice':
        choices.children[1].identity = 'kiosk-child-choice-9999'
    with pytest.raises(UiError):
        ui.run('kiosk-child-choices-open', '')
    for node in choices.children:
        node.action.do_action.assert_not_called()


def test_collapse_must_close_list_before_reading_unchanged_form():
    ui, _, choices, _ = disabled_accounts_form()
    choices.states.add('showing')
    with pytest.raises(UiError, match='timeout:kiosk-choices-closed'):
        ui.run('kiosk-child-choices-closed', '')
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-child-choices-closed', '')


def test_collapse_refuses_already_closed_list_without_reopening():
    ui, selector, _, _ = disabled_accounts_form()
    with pytest.raises(UiError, match='kiosk-choices-not-open'):
        ui.run('kiosk-child-choices-closed', '')
    selector.action.do_action.assert_not_called()


def test_inspection_refuses_already_open_list_without_collapsing():
    ui, selector, choices, _ = disabled_accounts_form()
    choices.states.add('showing')
    with pytest.raises(UiError, match='kiosk-choices-already-open'):
        ui.run('kiosk-child-choices-open', '')
    selector.action.do_action.assert_not_called()


def test_failed_open_readback_cannot_toggle_again():
    ui, selector, _, _ = disabled_accounts_form()
    selector.action.do_action.side_effect = lambda _: True
    with pytest.raises(UiError, match='timeout:kiosk-offered-accounts'):
        ui.run('kiosk-child-choices-open', '')
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-child-choices-open', '')
    selector.action.do_action.assert_called_once()


def test_collapse_refuses_new_prompt_without_input():
    ui, selector, choices, _ = disabled_accounts_form()
    choices.states.add('showing')
    ui.system_prompt_kind = Mock(return_value='polkit')
    with pytest.raises(UiError, match='system-prompt-refused'):
        ui.run('kiosk-child-choices-closed', '')
    selector.action.do_action.assert_not_called()


def test_controller_refuses_selection_changed_during_list_inspection():
    ui, *_ = disabled_accounts_form()
    result = ui.run('kiosk-request-form', '')
    result['operation'] = 'kiosk-child-choices-closed'
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe(result['operation']) == result
    result['request']['child'] = 'fixture-child'
    observer.call.return_value = (json.dumps(result).encode(), [])
    with pytest.raises(EvidenceError, match='ui:request'):
        observer.observe(result['operation'])


@pytest.mark.parametrize('settings', [
    {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
    {'child': 'fixture-child', 'limit_enabled': False, 'allowance': ['15 minutes']},
    {'child': 'existing-fixture-child', 'limit_enabled': False, 'allowance': ['0 minutes']},
])
def test_parent_baseline_drift_refuses_before_station_entry(settings):
    journey = InstalledJourney(SimpleNamespace(), Mock(), PLAN)
    with pytest.raises(EvidenceError, match='ui:settings-changed'):
        journey.check_settings('parent-selected', {'ui': {'settings': settings}})


@pytest.mark.parametrize('refusal', [None, *PLAN.screen_tags])
def test_worker_stops_at_every_failed_observation(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER.replace(
        'onpc_kiosk_eligible_choices', 'onpc_disabled_child')).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    if refusal:
        assert not result['ok']
        assert stages == expected[:expected.index(refusal) + 1]
        assert ['power', 'off'] not in result['events']
    else:
        assert result['ok'], result['error']
        assert stages == expected
        assert result['events'][-1] == ['power', 'off']
    assert ['key', 'esc'] not in result['events']
    assert not any('toggle' in operation or 'enabled' in operation
                   for operation in PLAN.screen_tags.values())


def test_callback_uses_complete_recorded_plan_and_finite_deadline(monkeypatch):
    import disabled_child
    record = Mock()
    monkeypatch.setattr(disabled_child, 'record_installed_journey', record)
    recorder, context = object(), object()
    disabled_child.E2E_CASES['disabled-child'](recorder, context)
    record.assert_called_once_with(recorder, context, PLAN, timeout=1800)
    assert set(PLAN.phases) == set(PLAN.stages)
    assert PLAN.advance_after == {
        'installed-greeter': 'step-1', 'request-form': 'step-2', 'child-selected': 'step-3'}
