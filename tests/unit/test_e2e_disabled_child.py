"""Case 57 preserves disabled policy and gates every input on public results."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import UiError
from disabled_child import PLAN
from installed_journey import InstalledJourney
from private_artifacts import EvidenceError
from tests.support.e2e_kiosk import WORKER, disabled_accounts_form
from tests.support.perl import run_perl
from ui_observations import RequestObservation


def test_selection_reads_disabled_result_without_activating_unavailable_controls():
    ui, selector, choices, _ = disabled_accounts_form()
    ui.run('kiosk-disabled-child-select', '')
    after = ui.run('kiosk-disabled-form', '')
    observed = RequestObservation.from_request(after['request'], operation='kiosk-disabled-form')
    assert observed.child == 'fixture-child'
    assert not observed.approver_selector_enabled and not observed.request_enabled
    assert selector.action.do_action.call_count == 1
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
        ui.run('kiosk-disabled-child-select', '')
    for node in choices.children:
        node.action.do_action.assert_not_called()


def test_failed_open_readback_cannot_toggle_again():
    ui, selector, _, _ = disabled_accounts_form()
    # Acknowledge the canonical setter without updating the selected account.
    selector.setValue.side_effect = lambda _: None
    with pytest.raises(UiError, match='timeout:kiosk-selected-account'):
        ui.run('kiosk-disabled-child-select', '')
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-disabled-child-select', '')
    selector.setValue.assert_called_once_with('1001')
    selector.action.do_action.assert_not_called()


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
