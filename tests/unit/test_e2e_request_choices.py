"""Disabled availability must follow saved preparation and fresh public reads."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import CHILD, UiError
from private_artifacts import EvidenceError
from tests.support.e2e_kiosk import WORKER, accounts_form, disabled_accounts_form
from tests.support.perl import run_perl
from ui_observations import RequestObservation, UiObservations


def test_disabled_selection_and_independent_read_never_activate_disabled_controls():
    ui, selector, choices, _ = disabled_accounts_form()
    selected = ui.run('kiosk-disabled-child-select', '')
    read = ui.run('kiosk-disabled-form', '')
    for result in (selected, read):
        observation = RequestObservation.from_request(result['request'], operation=result['operation'])
        assert observation.child == 'fixture-child'
        assert observation.approver == 'other-fixture-parent'
        assert observation.message == 'screen-limit-disabled'
        assert not observation.request_enabled
        assert not observation.approver_selector_enabled
    selector.action.do_action.assert_called_once()
    choices.children[0].action.do_action.assert_called_once()
    for identity in ('kiosk-approver-selector', 'kiosk-request-submit',
                     'kiosk-soft-apps-toggle', 'kiosk-duration-1800'):
        ui.find_id(identity).action.do_action.assert_not_called()


@pytest.mark.parametrize('field,value', [
    ('request_enabled', True), ('approver_selector_enabled', True),
    ('duration_enabled', True), ('soft_choice_enabled', True),
    ('message', ''), ('child', 'existing-fixture-child'), ('approver', ''),
])
def test_controller_rejects_wrong_disabled_result(field, value):
    ui, *_ = disabled_accounts_form()
    result = ui.run('kiosk-disabled-child-select', '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe(result['operation']) == result
    result['request'][field] = value
    observer.call.return_value = (json.dumps(result).encode(), [])
    with pytest.raises(EvidenceError, match='ui:request'):
        observer.observe(result['operation'])


def test_disabled_binding_refuses_enabled_result_without_replaying_input():
    ui, selector, choices, expected = accounts_form()
    with pytest.raises(UiError, match='kiosk-duration-availability'):
        ui.select_kiosk_account('child', CHILD, expected=expected, enabled=False)
    with pytest.raises(UiError, match='uncertain-input'):
        ui.select_kiosk_account('child', CHILD, expected=expected, enabled=False)
    selector.action.do_action.assert_called_once()
    choices.children[0].action.do_action.assert_called_once()


def test_invalid_expected_availability_refuses_before_input():
    ui, selector, _, expected = disabled_accounts_form()
    with pytest.raises(UiError, match='kiosk-enabled-binding'):
        ui.select_kiosk_account('child', CHILD, expected=expected, enabled=0)
    selector.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['kiosk-disabled-child-select', 'kiosk-disabled-form'])
def test_authentication_prompt_refuses_without_input(operation):
    ui, selector, choices, _ = disabled_accounts_form()
    ui.system_prompt_kind = Mock(return_value='polkit')
    with pytest.raises(UiError, match='system-prompt-refused:station:polkit'):
        ui.run(operation, '')
    selector.action.do_action.assert_not_called()
    choices.children[0].action.do_action.assert_not_called()


def test_qualification_reuses_guarded_snapshot(tmp_path):
    from parent_setup_qualification import RequestChoicesQualification, KioskEntryQualification
    from request_choices import PLAN
    context = SimpleNamespace(directory=tmp_path)
    assert RequestChoicesQualification.journey(context, Mock()).plan is PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert RequestChoicesQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot


@pytest.mark.parametrize('conflict', ['kiosk_eligible_choices', 'parent_toggle', 'kiosk_entry'])
def test_conflicting_modes_refuse_before_vm_access(conflict):
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='request-choices-prerequisites'):
        smoke.main(assets='/unused', provision_credentials=True,
                   request_choices=True, **{conflict: True})


@pytest.mark.parametrize('refusal', [None, 'save-disabled', 'child-selected', 'availability-read'])
def test_worker_stops_at_failed_public_result(monkeypatch, refusal):
    from request_choices import PLAN
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_choices')).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    if refusal:
        assert not result['ok']
        assert stages == expected[:expected.index(refusal) + 1]
    else:
        assert result['ok'], result['error']
        assert stages == expected
        assert result['events'][-1] == ['power', 'off']
