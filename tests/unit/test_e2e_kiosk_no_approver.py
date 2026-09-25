"""No-approver public evidence and fixed qualification boundaries."""

import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import UiError
from kiosk_no_approver import CASE_PLAN, PLAN
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node
from tests.support.e2e_kiosk import WORKER, request_form
from tests.support.perl import run_perl
from ui_observations import RequestObservation, UiObservations


def empty_form():
    ui, _ = request_form()
    selector = ui.find_id('kiosk-approver-selector')
    selector.children[0].identity = 'kiosk-approver-selected-none'
    selector.children[0].name = ''
    selector.description = 'Choose the approving parent.'
    form = ui.find_id('kiosk-request-form')
    status = Node('No local interactive administrator accounts are available.',
                  identity='kiosk-request-status')
    status.parent = form
    form.children.append(status)
    return ui


def test_empty_approver_result_is_exact_and_read_only():
    ui = empty_form()
    for _ in range(2):
        result = ui.run('kiosk-no-approver-form', '')
        observation = RequestObservation.from_request(
            result['request'], operation='kiosk-no-approver-form')
        assert observation.approver == 'none'
        assert observation.child == 'existing-fixture-child'
        assert observation.message == 'no-approver'
        assert not observation.request_enabled
    for node in ui.nodes(strict=True):
        node.action.do_action.assert_not_called()
        node.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', [
    'approver', 'hidden-approver', 'selected-approver', 'duplicate-none', 'hidden-none',
    'wrong-message', 'missing-message', 'duplicate-message', 'wrong-owner',
    'wrong-surface', 'request-enabled', 'duration-enabled', 'approver-enabled',
    'soft-enabled', 'no-child', 'stale', 'incomplete', 'prompt',
])
def test_refuses_incorrect_or_incomplete_public_evidence(fault):
    ui = empty_form()
    form = ui.find_id('kiosk-request-form')
    if fault in ('approver', 'hidden-approver', 'duplicate-message'):
        node = Node(identity='kiosk-request-status' if fault == 'duplicate-message'
                    else 'kiosk-approver-choice-1000',
                    states=() if fault == 'hidden-approver' else ('showing', 'visible'))
        node.parent = form
        form.children.append(node)
    elif fault == 'selected-approver':
        ui.find_id('kiosk-approver-selected-none').identity = 'kiosk-approver-selected-1010'
    elif fault == 'duplicate-none':
        selector = ui.find_id('kiosk-approver-selector')
        node = Node(identity='kiosk-approver-selected-none')
        node.parent = selector
        selector.children.append(node)
    elif fault == 'hidden-none':
        ui.find_id('kiosk-approver-selected-none').states.clear()
    elif fault == 'wrong-message':
        ui.find_id('kiosk-request-status').name = 'Screen limit is not enabled in Parent App'
    elif fault == 'missing-message':
        ui.find_id('kiosk-request-status').identity = 'unrelated'
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    elif fault == 'wrong-surface':
        ui.find_id('kiosk-request-window').identity = 'parent-window'
    elif fault.endswith('-enabled'):
        identity = {'request': 'request-submit', 'duration': 'duration-1800',
                    'approver': 'approver-selector', 'soft': 'soft-apps-toggle'}[fault[:-8]]
        ui.find_id('kiosk-' + identity).states.add('sensitive')
    elif fault == 'no-child':
        ui.find_id('kiosk-child-selected-1002').identity = 'kiosk-child-selected-none'
    elif fault == 'stale':
        form.states.add('defunct')
    elif fault == 'incomplete':
        form.children.append(None)
    elif fault == 'prompt':
        ui.system_prompt_kind = Mock(return_value='polkit')
    with pytest.raises((UiError, EvidenceError)):
        result = ui.run('kiosk-no-approver-form', '')
        RequestObservation.from_request(result['request'], operation='kiosk-no-approver-form')


def test_controller_rejects_nonempty_or_enabled_projection():
    result = empty_form().run('kiosk-no-approver-form', '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe('kiosk-no-approver-form') == result
    for field, value in (('approver', 'fixture-parent'), ('child', 'none'),
                         ('request_enabled', True), ('message', 'screen-limit-disabled')):
        broken = {**result, 'request': {**result['request'], field: value}}
        observer.call.return_value = json.dumps(broken).encode(), []
        with pytest.raises(EvidenceError, match='ui:request'):
            observer.observe('kiosk-no-approver-form')


def test_wrong_entry_requires_absent_station_and_expected_refusal():
    ui = empty_form()
    # Exercise the successful snapshot branch deliberately; the real empty
    # selector is disabled and would already refuse as unavailable.
    ui.find_id('kiosk-approver-selector').states.add('sensitive')
    ui.gdm_nonsecret_account = Mock()
    with pytest.raises(UiError, match='wrong-entry-accepted'):
        ui.run('gdm-no-approver-refused', '')
    ui.kiosk_account_snapshot = Mock(side_effect=UiError('ui:kiosk-account-surface'))
    assert ui.run('gdm-no-approver-refused', '')['outcome'] == 'passed'
    ui.kiosk_account_snapshot.assert_called_once_with('approver')
    ui.kiosk_account_snapshot.side_effect = UiError('ui:wrong-owner')
    with pytest.raises(UiError, match='wrong-refusal'):
        ui.run('gdm-no-approver-refused', '')


def test_qualification_reuses_snapshot_observed_fixture_and_outer_cleanup(tmp_path):
    from parent_setup_qualification import KioskNoApproverQualification, KioskEntryQualification
    context = SimpleNamespace(directory=tmp_path, lease=SimpleNamespace(state={'run': 'a' * 32}))
    journey = KioskNoApproverQualification.journey(context, Mock())
    assert journey.plan is PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert KioskNoApproverQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert KioskNoApproverQualification.finalize is KioskEntryQualification.finalize
    assert PLAN.stage_actions == {'baseline-approvers': 'prepare-no-approver'}
    journey.transport = Mock()
    journey.ui = SimpleNamespace(last_operation='kiosk-approver-baseline', approver_uids=(3210,))
    journey.transport.call.return_value = b'onpc-e2e: stage=no-approver outcome=prepared locked=1\n'
    action = journey.actions['prepare-no-approver']
    assert action(journey, Mock()) == {'eligible_approvers_removed': 1}
    assert json.loads(journey.transport.call.call_args.kwargs['input']) == [3210]
    assert journey.ui.approver_uids is None
    assert journey.transport.call.call_args.args[0][-1] == 'prepare-no-approver'
    with pytest.raises(EvidenceError, match='controller-state'):
        action(journey, Mock())
    journey.transport.call.assert_called_once()


def test_every_conflicting_mode_refuses_before_vm_access(monkeypatch):
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    credentials = Mock(side_effect=AssertionError('conflict reached credential preparation'))
    storage = Mock(side_effect=AssertionError('conflict reached VM run allocation'))
    monkeypatch.setattr(smoke, 'FixtureCredentials', credentials)
    monkeypatch.setattr(smoke, 'storage_session', storage)
    for name in inspect.signature(smoke.main).parameters:
        if name in ('assets', 'provision_credentials', 'kiosk_no_approver'):
            continue
        # Either conflicting mode may be validated first. The safety contract
        # is refusal before preparation, independent of validator source order.
        with pytest.raises(CommandError, match=r'^smoke:[a-z-]+-prerequisites$'):
            smoke.main(assets='/unused', provision_credentials=True,
                       kiosk_no_approver=True, **{name: 'parent' if name == 'fresh_desktop' else True})
    credentials.assert_not_called()
    storage.assert_not_called()


@pytest.mark.parametrize('refusal', [None, *PLAN.screen_tags])
def test_worker_requires_every_result_without_authentication(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER.replace(
        'onpc_kiosk_eligible_choices', 'onpc_kiosk_no_approver').replace(
            "$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    assert not any(event[0] == 'secret' for event in result['events'])
    if refusal:
        assert not result['ok']
        assert stages == expected[:expected.index(refusal) + 1]
        assert ['power', 'off'] not in result['events']
    else:
        assert result['ok'], result['error']
        assert stages == expected
        assert result['events'][-1] == ['power', 'off']


def baseline_form(uids):
    ui, _ = request_form()
    selector = ui.find_id('kiosk-approver-selector')
    # GTK omits collapsed choices. The showing selection proves a nonempty form.
    selector.children[0].identity = f'kiosk-approver-selected-{uids[0] if uids else "none"}'
    return ui, selector


@pytest.mark.parametrize('refusal', [None, *CASE_PLAN.screen_tags])
def test_complete_case_stops_at_each_failed_result(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER.replace(
        'onpc_kiosk_eligible_choices', 'onpc_no_parent').replace(
            "$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")).stdout)
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


def test_complete_callback_owns_fresh_observed_fixture_and_deadline(monkeypatch):
    import kiosk_no_approver
    record = Mock()
    monkeypatch.setattr(kiosk_no_approver, 'record_installed_journey', record)
    recorder, context = object(), SimpleNamespace(
        lease=SimpleNamespace(state={'run': 'a' * 32}))
    for _ in range(2):
        kiosk_no_approver.E2E_CASES['no-parent'](recorder, context)
        args, kwargs = record.call_args
        assert args == (recorder, context, CASE_PLAN)
        assert kwargs['timeout'] == 1800
        journey = SimpleNamespace(context=context, transport=Mock(), ui=SimpleNamespace(
            last_operation='kiosk-approver-baseline', approver_uids=(3210, 4321)))
        journey.transport.call.return_value = b'onpc-e2e: stage=no-approver outcome=prepared locked=3\n'
        prepare = kwargs['actions']['prepare-no-approver']
        assert prepare(journey, Mock()) == {'eligible_approvers_removed': 3}
        assert json.loads(journey.transport.call.call_args.kwargs['input']) == [3210, 4321]
        with pytest.raises(EvidenceError, match='controller-state'):
            prepare(journey, Mock())
        journey.transport.call.assert_called_once()
    assert set(CASE_PLAN.phases) == set(CASE_PLAN.stages)
    assert CASE_PLAN.advance_after == {
        'station-list': 'step-1', 'cancel-station-branch': 'step-2', 'empty-form': 'step-3'}
    assert CASE_PLAN.stage_actions == {'baseline-approvers': 'prepare-no-approver'}


@pytest.mark.parametrize('uids', [[5432], [5432, 6543], list(range(3000, 3017))])
def test_baseline_accepts_any_listed_parent_without_input(uids):
    ui, _ = baseline_form(uids)
    result = ui.run('kiosk-approver-baseline', '')
    assert result['approver_uids'] == uids[:1]
    for node in ui.nodes(strict=True):
        node.action.do_action.assert_not_called()
        node.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['empty', 'missing-selection', 'bad-id',
                                  'low-uid', 'high-uid',
                                  'hidden-selected', 'duplicate-selected',
                                  'wrong-owner', 'wrong-surface', 'incomplete', 'stale', 'prompt'])
def test_baseline_refuses_missing_or_ambiguous_public_evidence(fault):
    ui, selector = baseline_form([] if fault == 'empty' else [5432])
    if fault == 'missing-selection': selector.children.clear()
    if fault == 'bad-id': selector.children[0].identity = 'kiosk-approver-selected-garbage'
    if fault == 'low-uid': selector.children[0].identity = 'kiosk-approver-selected-0'
    if fault == 'high-uid': selector.children[0].identity = f'kiosk-approver-selected-{2 ** 32}'
    if fault == 'hidden-selected': selector.children[0].states.clear()
    if fault == 'duplicate-selected': selector.children.append(Node(identity='kiosk-approver-selected-5432'))
    if fault == 'wrong-owner': ui.owner_pids = lambda: {999}
    if fault == 'wrong-surface': ui.find_id('kiosk-request-window').identity = 'parent-window'
    if fault == 'incomplete': selector.children.append(None)
    if fault == 'stale': selector.states.add('defunct')
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='polkit')
    with pytest.raises(UiError):
        ui.run('kiosk-approver-baseline', '')


def test_baseline_controller_keeps_only_presence_in_durable_evidence():
    ui, _ = baseline_form([5432, 6543])
    result = ui.run('kiosk-approver-baseline', '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    sanitized = observer.observe('kiosk-approver-baseline')
    assert sanitized == {'operation': 'kiosk-approver-baseline', 'outcome': 'passed',
                         'interface': 'AT-SPI', 'approver_present': True}
    assert observer.approver_uids == (5432,)
    observer.call.return_value = b'{}', []
    with pytest.raises(EvidenceError):
        observer.observe('kiosk-no-approver-form')
    assert observer.approver_uids is None


@pytest.mark.parametrize('uids', [[], [True], [5432, 5432], ['5432'], [999], [2 ** 32]])
def test_baseline_controller_rejects_invalid_reply(uids):
    observer = UiObservations(Mock())
    result = {'operation': 'kiosk-approver-baseline', 'outcome': 'passed',
              'interface': 'AT-SPI', 'approver_uids': uids}
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises(EvidenceError, match='approver-baseline'):
        observer.observe('kiosk-approver-baseline')
    assert observer.approver_uids is None
