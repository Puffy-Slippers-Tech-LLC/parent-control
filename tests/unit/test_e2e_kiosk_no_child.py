"""No-child profile: exact public results, refusals and guarded composition."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node
from tests.support.e2e_kiosk import WORKER, request_form
from tests.support.perl import run_perl
from ui_observations import RequestObservation, UiObservations
from kiosk_no_child import CASE_PLAN


def empty_form():
    ui, _ = request_form()
    child = ui.find_id('kiosk-child-selector')
    child.children[0].identity = 'kiosk-child-selected-none'
    child.children[0].name = ''
    child.description = 'Choose the child account.'
    status = ui.find_id('kiosk-screen-limit-notice')
    status.identity = 'kiosk-request-status'
    status.name = 'No local standard accounts are available. Create one, then reopen this screen.'
    return ui


def test_empty_form_is_exact_and_read_only():
    ui = empty_form()
    nodes = list(ui.nodes(strict=True))
    for _ in range(2):
        result = ui.run('kiosk-no-child-form', '')
        observation = RequestObservation.from_request(result['request'], operation='kiosk-no-child-form')
        assert observation.child == 'none'
        assert observation.approver == 'other-fixture-parent'
        assert observation.message == 'no-child'
        assert not observation.request_enabled
    for node in nodes:
        node.action.do_action.assert_not_called()
        node.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['child', 'hidden-child', 'selected-child', 'duplicate-none',
    'wrong-message', 'wrong-owner', 'wrong-surface', 'missing-message', 'duplicate-message',
    'request-enabled', 'duration-enabled', 'stale', 'incomplete', 'prompt'])
def test_empty_state_refuses_invalid_public_evidence(fault):
    ui = empty_form()
    form = ui.find_id('kiosk-request-form')
    if fault in ('child', 'hidden-child'):
        node = Node(identity='kiosk-child-choice-1001', states=() if fault == 'hidden-child'
                    else ('showing', 'visible', 'sensitive'))
        node.parent = form
        form.children.append(node)
    elif fault == 'selected-child':
        ui.find_id('kiosk-child-selected-none').identity = 'kiosk-child-selected-1001'
    elif fault == 'duplicate-none':
        child = ui.find_id('kiosk-child-selector')
        node = Node(identity='kiosk-child-selected-none')
        node.parent = child
        child.children.append(node)
    elif fault == 'wrong-message':
        ui.find_id('kiosk-request-status').name = 'Screen limit is not enabled in Parent App'
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    elif fault == 'wrong-surface':
        ui.find_id('kiosk-request-window').identity = 'parent-window'
    elif fault == 'missing-message':
        ui.find_id('kiosk-request-status').identity = 'unrelated'
    elif fault == 'duplicate-message':
        node = Node(identity='kiosk-request-status')
        node.parent = form
        form.children.append(node)
    elif fault == 'request-enabled':
        ui.find_id('kiosk-request-submit').states.add('sensitive')
    elif fault == 'duration-enabled':
        ui.find_id('kiosk-duration-1800').states.add('sensitive')
    elif fault == 'stale':
        form.states.add('defunct')
    elif fault == 'incomplete':
        form.children.append(None)
    elif fault == 'prompt':
        ui.system_prompt_kind = Mock(return_value='polkit')
    with pytest.raises((UiError, EvidenceError)):
        result = ui.run('kiosk-no-child-form', '')
        RequestObservation.from_request(result['request'], operation='kiosk-no-child-form')


def test_controller_rejects_nonempty_or_enabled_projection():
    result = empty_form().run('kiosk-no-child-form', '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe('kiosk-no-child-form') == result
    for field, value in (('child', 'fixture-child'), ('request_enabled', True),
                         ('message', 'screen-limit-disabled')):
        broken = {**result, 'request': {**result['request'], field: value}}
        observer.call.return_value = json.dumps(broken).encode(), []
        with pytest.raises(EvidenceError, match='ui:request'):
            observer.observe('kiosk-no-child-form')


def test_wrong_entry_refusal_requires_absent_station_surface():
    ui = empty_form()
    ui.gdm_nonsecret_account = Mock()
    with pytest.raises(UiError, match='wrong-entry-accepted'):
        ui.run('gdm-no-child-refused', '')
    ui.kiosk_account_snapshot = Mock(side_effect=UiError('ui:kiosk-account-surface'))
    assert ui.run('gdm-no-child-refused', '')['outcome'] == 'passed'
    ui.kiosk_account_snapshot.side_effect = UiError('ui:wrong-owner')
    with pytest.raises(UiError, match='wrong-refusal'):
        ui.run('gdm-no-child-refused', '')


def test_qualification_reuses_snapshot_and_fixed_fixture(tmp_path):
    from kiosk_no_child import PLAN
    from parent_setup_qualification import KioskNoChildQualification, KioskEntryQualification
    context = SimpleNamespace(directory=tmp_path, lease=SimpleNamespace(state={'run': 'a' * 32}))
    journey = KioskNoChildQualification.journey(context, Mock())
    assert journey.plan is PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert KioskNoChildQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert PLAN.stage_actions == {'setup-detached': 'prepare-empty'}
    journey.transport = Mock()
    journey.transport.call.return_value = b'onpc-e2e: stage=empty-account outcome=prepared\n'
    action = journey.actions['prepare-empty']
    assert action(journey, Mock()) == {'eligible_accounts_removed': 2}
    assert journey.transport.call.call_args.args[0][-1] == 'prepare-empty'
    with pytest.raises(EvidenceError, match='controller-state'):
        action(journey, Mock())
    journey.transport.call.assert_called_once()


@pytest.mark.parametrize('conflict', ['kiosk_eligible_choices', 'request_choices', 'kiosk_entry',
                                     'parent_toggle', 'license_viewer_provider'])
def test_conflicting_modes_refuse_before_vm_access(conflict):
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='kiosk-no-child-prerequisites'):
        smoke.main(assets='/unused', provision_credentials=True,
                   kiosk_no_child=True, **{conflict: True})


@pytest.mark.parametrize('refusal', [None, 'wrong-entry', 'empty-form', 'empty-rechecked'])
def test_worker_requires_all_results_without_authentication(monkeypatch, refusal):
    from kiosk_no_child import PLAN
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_kiosk_no_child')).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    assert not any(event[0] == 'secret' for event in result['events'])
    if refusal:
        assert not result['ok']
        assert stages == expected[:expected.index(refusal) + 1]
    else:
        assert result['ok'], result['error']
        assert stages == expected
        assert result['events'][-1] == ['power', 'off']


@pytest.mark.parametrize('refusal', [None, *CASE_PLAN.screen_tags])
def test_complete_case_stops_at_each_failed_result(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER.replace(
        'onpc_kiosk_eligible_choices', 'onpc_no_child')).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(CASE_PLAN.screen_tags)
    assert 'wrong-entry' not in stages
    assert not any(event[0] == 'secret' for event in result['events'])
    if refusal:
        assert not result['ok']
        assert stages == expected[:expected.index(refusal) + 1]
        assert ['power', 'off'] not in result['events']
    else:
        assert result['ok'], result['error']
        assert stages == expected
        assert result['events'][-1] == ['power', 'off']


def test_complete_callback_owns_fresh_fixture_and_deadline(monkeypatch):
    import kiosk_no_child
    record = Mock()
    monkeypatch.setattr(kiosk_no_child, 'record_installed_journey', record)
    recorder, context = object(), SimpleNamespace(
        lease=SimpleNamespace(state={'run': 'a' * 32}))
    for _ in range(2):
        kiosk_no_child.E2E_CASES['no-child'](recorder, context)
        args, kwargs = record.call_args
        assert args == (recorder, context, CASE_PLAN)
        assert kwargs['timeout'] == 1800
        journey = SimpleNamespace(context=context, transport=Mock())
        journey.transport.call.return_value = b'onpc-e2e: stage=empty-account outcome=prepared\n'
        prepare = kwargs['actions']['prepare-empty']
        assert prepare(journey, Mock()) == {'eligible_accounts_removed': 2}
        with pytest.raises(EvidenceError, match='controller-state'):
            prepare(journey, Mock())
        journey.transport.call.assert_called_once()
    assert set(CASE_PLAN.phases) == set(CASE_PLAN.stages)
    assert CASE_PLAN.advance_after == {
        'station-list': 'step-1', 'station-branch': 'step-2', 'empty-form': 'step-3'}


def test_empty_form_cancel_uses_only_enabled_cancel_control():
    ui = empty_form()
    ui.run('kiosk-no-child-form', '')
    ui.run('kiosk-request-cancel', '')
    ui.find_id('kiosk-request-cancel').action.do_action.assert_called_once()
    for identity in ('kiosk-request-submit', 'kiosk-child-selector',
                     'kiosk-approver-selector', 'kiosk-duration-1800'):
        ui.find_id(identity).action.do_action.assert_not_called()
