"""Valid kiosk choices: private tree doubles and bounded Perl child only.

No shared files, buses, displays, sockets or fixture builds; unit-compatible.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import accounts_form, WORKER
from tests.support.perl import run_perl
from ui_observations import UiObservations, RequestObservation
from kiosk_valid_duration import PLAN, KioskValidDurationJourney
from request_duration import PLAN as INVALID_PLAN
from request_flow import PLAN as FLOW_PLAN, CHOICES, prepared_request, RequestFlowJourney
from kiosk_cancel import PLAN as CANCEL_PLAN


def valid_form():
    ui, _, choices, _ = accounts_form('approver')
    choices.children[0].action.do_action(0)
    form = ui.find_id('kiosk-request-form')
    status = Node('Estimated time remaining if approved: 45m', 'label', identity='kiosk-request-status')
    custom = Node('Custom minutes', 'entry', identity='kiosk-custom-duration', states=('visible', 'sensitive', 'editable'))
    custom.value = '1.25'
    custom.get_text_iface = lambda: SimpleNamespace(
        get_character_count=lambda: len(custom.value), get_text=lambda start, end: custom.value[start:end])
    ui.api.Text = SimpleNamespace(get_character_count=lambda interface: interface.get_character_count(),
                                  get_text=lambda interface, start, end: interface.get_text(start, end))
    for node in (status, custom):
        node.parent = form
        form.children.append(node)
    for value in (300, 900, 1800, 3600, 7200, 14400, 0, 'custom'):
        node = ui.find_id(f'kiosk-duration-{value}')
        def select(_index, value=value):
            for other in form.children:
                if other.identity.startswith('kiosk-duration-'):
                    other.states.discard('pressed')
            ui.find_id(f'kiosk-duration-{value}').states.add('pressed')
            if value == 'custom':
                custom.states.add('showing')
                status.name = 'Estimated time remaining if approved: 16m 15s'
            else:
                custom.states.discard('showing')
                status.name = ('If approved, access until midnight.' if value == 0 else
                               'Estimated time remaining if approved: 20m')
            return True
        node.action.do_action.side_effect = select
    soft = ui.find_id('kiosk-soft-apps-toggle')
    def toggle(_):
        soft.states.symmetric_difference_update({'checked'})
        return True
    soft.action.do_action.side_effect = toggle
    return ui, status, custom


def test_public_choices_roundtrip_through_real_controller_decoder():
    ui, status, custom = valid_form()
    observer = UiObservations(Mock())
    operations = ['kiosk-valid-preset-select', 'kiosk-valid-preset-read',
                  'kiosk-valid-custom-open', 'kiosk-valid-fraction-read',
                  'kiosk-valid-rest-select', 'kiosk-valid-rest-read',
                  'kiosk-valid-soft-select', 'kiosk-valid-soft-read',
                  'kiosk-valid-excluded-select', 'kiosk-valid-excluded-read']
    for operation in operations:
        result = ui.run(operation, '')
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        assert observer.observe(operation) == result
        if 'valid_choice' in result:
            RequestObservation.from_request(result['valid_choice']['request'], operation=operation)
    ui.find_id('kiosk-request-submit').action.do_action.assert_not_called()
    assert ui.find_id('kiosk-soft-apps-toggle').action.do_action.call_count == 2
    ui.kiosk_valid_choice('kiosk-valid-excluded-select')
    assert ui.find_id('kiosk-soft-apps-toggle').action.do_action.call_count == 2


@pytest.mark.parametrize('fault', ['wrong-child', 'wrong-approver', 'disabled', 'hidden',
                                  'duplicate', 'wrong-owner', 'incomplete', 'wrong-entry'])
def test_refuses_bad_input_boundary(fault):
    ui, _, _ = valid_form()
    target = ui.find_id('kiosk-duration-300')
    if fault in ('wrong-child', 'wrong-approver'):
        field = fault.removeprefix('wrong-')
        ui.find_id(f'kiosk-{field}-selector').children[0].identity = f'kiosk-{field}-selected-9999'
    elif fault in ('disabled', 'hidden'):
        target.states.discard('sensitive' if fault == 'disabled' else 'visible')
    elif fault == 'duplicate':
        ui.find_id('kiosk-request-form').children.append(Node(identity=target.identity))
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    elif fault == 'incomplete':
        ui.find_id('kiosk-request-form').children.append(None)
    else:
        ui.find_id('kiosk-request-window').identity = 'parent-window'
    with pytest.raises(UiError):
        ui.kiosk_valid_choice('kiosk-valid-preset-select')
    target.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['uncertain', 'unchanged', 'wrong-estimate'])
def test_input_without_valid_result_is_terminal(fault):
    ui, status, _ = valid_form()
    target = ui.find_id('kiosk-duration-300')
    if fault == 'uncertain':
        target.action.do_action.side_effect = RuntimeError('lost reply')
    elif fault == 'unchanged':
        target.action.do_action.side_effect = None
    else:
        original = target.action.do_action.side_effect
        def bad(index):
            original(index)
            status.name = 'Time estimate unavailable'
            return True
        target.action.do_action.side_effect = bad
    with pytest.raises((UiError, RuntimeError)):
        ui.kiosk_valid_choice('kiosk-valid-preset-select')
    with pytest.raises(UiError, match='uncertain-input'):
        ui.kiosk_valid_choice('kiosk-valid-preset-select')
    target.action.do_action.assert_called_once()


def test_custom_value_is_exact_and_foreign_text_is_not_returned():
    ui, _, custom = valid_form()
    ui.kiosk_valid_choice('kiosk-valid-custom-open')
    custom.value = '1.5'
    with pytest.raises(UiError, match='kiosk-custom-value'):
        ui.kiosk_valid_choice('kiosk-valid-fraction-read')


@pytest.mark.parametrize('result', ['revealed', 'missing', 'disabled', 'prompt'])
def test_custom_open_waits_for_public_reveal_without_replaying_input(result):
    ui, _, custom = valid_form()
    form = ui.find_id('kiosk-request-form')
    button = ui.find_id('kiosk-duration-custom')
    select = button.action.do_action.side_effect
    def delayed(index):
        select(index)
        form.children.remove(custom)
        return True
    button.action.do_action.side_effect = delayed
    reads = []
    def dispatch():
        reads.append(True)
        if len(reads) == 2 and result != 'missing':
            form.children.append(custom)
            if result == 'disabled':
                custom.states.discard('sensitive')
            if result == 'prompt':
                ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
        return False
    ui.dispatch = dispatch
    ui.timeout = .3
    if result == 'revealed':
        ui.run('kiosk-valid-custom-open', '')
        assert len(reads) >= 2
    else:
        expected = {'missing': 'timeout:kiosk-custom-open',
                    'disabled': 'kiosk-valid-disabled',
                    'prompt': 'system-prompt-refused'}[result]
        with pytest.raises(UiError, match=expected):
            ui.run('kiosk-valid-custom-open', '')
        with pytest.raises(UiError, match='uncertain-input'):
            ui.kiosk_valid_choice('kiosk-valid-custom-open')
    button.action.do_action.assert_called_once()
    ui.find_id('kiosk-request-submit').action.do_action.assert_not_called()


def test_custom_text_focus_uses_owned_surface_action_and_exact_readback():
    ui, _, custom = valid_form()
    ui.kiosk_valid_choice('kiosk-valid-custom-open')
    window = ui.find_id('kiosk-request-window')
    window.states.add('active')
    window.action.get_action_name = lambda _: 'focus.kiosk-custom-duration'
    window.action.do_action.side_effect = lambda _: custom.states.add('focused') or True
    ui.run('text-kiosk-fraction-focus', '')
    ui.run('text-kiosk-fraction-selected', '')
    result = ui.run('text-kiosk-fraction-read', '')
    assert result['text']['exact']
    window.action.do_action.assert_called_once()


def test_wrong_entry_refusal_has_no_input():
    ui = ui_for(Node(identity='parent-window'))
    ui.run('parent-kiosk-valid-refused', '')


def test_prompt_refuses_before_duration_input():
    ui, _, _ = valid_form()
    ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
    with pytest.raises(UiError, match='system-prompt-refused'):
        ui.run('kiosk-valid-preset-select', '')
    ui.find_id('kiosk-duration-300').action.do_action.assert_not_called()


@pytest.mark.parametrize('change', ['child', 'seconds', 'soft', 'estimate', 'timestamp'])
def test_decoder_rejects_mutated_projection(change):
    ui, _, _ = valid_form()
    result = ui.run('kiosk-valid-preset-select', '')
    value = result['valid_choice']
    if change == 'child':
        value['request']['child'] = 'existing-fixture-child'
    elif change == 'seconds':
        value['request']['duration_seconds'] = 900
    elif change == 'soft':
        value['request']['allow_soft'] = True
    elif change == 'estimate':
        value['estimate']['seconds'] += 1
    else:
        value['observed_monotonic_ns'] = 0
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises((EvidenceError, UiError)):
        observer.observe('kiosk-valid-preset-select')


@pytest.mark.parametrize('seconds,passed', [(1200, True), (1500, False), (900, False)])
def test_estimate_uses_prior_public_balance(seconds, passed):
    journey = object.__new__(KioskValidDurationJourney)
    journey.plan = PLAN
    journey.balance = {'daily': {'seconds': 900, 'precision_seconds': 1},
                       'one_time': {'seconds': 0, 'precision_seconds': 1},
                       'observed_monotonic_ns': 1_000_000_000}
    observed = {'ui': {'valid_choice': {
        'request': {'duration_seconds': 300}, 'estimate': {'kind': 'fixed', 'seconds': seconds},
        'observed_monotonic_ns': 121_000_000_000}}}
    if passed:
        journey.check_settings('kiosk-valid-preset-read', observed)
        assert observed['comparison']['estimate_bounds']
    else:
        with pytest.raises(EvidenceError, match='kiosk-valid:'):
            journey.check_settings('kiosk-valid-preset-read', observed)


@pytest.mark.parametrize('refusal', [None, 'valid-wrong-entry', 'kiosk-valid-preset-read',
                                  'text-kiosk-fraction-selected', 'kiosk-valid-soft-read'])
def test_worker_order_and_refusal(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_kiosk_valid_duration').replace(
        "sub record_info { }", "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])


@pytest.mark.parametrize('conflict', ['request_choices', 'allowance', 'kiosk_entry'])
def test_mode_conflicts_refuse_before_vm(conflict):
    import check_graphical_smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='kiosk-valid-duration-prerequisites'):
        check_graphical_smoke.main(assets='/unused', provision_credentials=True,
                                  kiosk_valid_duration=True, **{conflict: True})


def test_qualification_reuses_snapshot_and_ledger(tmp_path):
    from parent_setup_qualification import KioskValidDurationQualification, KioskEntryQualification
    journey = KioskValidDurationQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is PLAN
    # Parent opens this section expanded; setup observes it without a toggle.
    assert 'ui:time-explanation-expand' not in PLAN.screen_tags.values()
    assert PLAN.screen_tags['time-explanation-read'] == 'ui:time-explanation-read'
    assert KioskValidDurationQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot


@pytest.mark.parametrize('binding,value', list(accessible_ui.KIOSK_INVALID_VALUES.items()))
def test_invalid_submission_preserves_exact_form_and_decodes(binding, value):
    ui, status, custom = valid_form()
    ui.run('kiosk-valid-custom-open', '')
    custom.value = value
    submit = ui.find_id('kiosk-request-submit')
    def validate(_):
        status.name = 'Enter a number from 0.1 to 1440 minutes.'
        return True
    submit.action.do_action.side_effect = validate
    observer = UiObservations(Mock())
    for action in ('ready', 'submit', 'read'):
        operation = f'kiosk-invalid-{binding}-{action}'
        result = ui.run(operation, '')
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        assert observer.observe(operation) == result
        projection = result['invalid_choice']
        assert projection['request']['custom_text'] == value
        assert projection['request']['duration_seconds'] is None
        assert projection['request']['request_enabled'] is True
        assert projection['validation'] is (action != 'ready')
    submit.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['disabled', 'wrong-child', 'wrong-value', 'prompt',
                                  'uncertain', 'no-validation', 'changed-form', 'prompt-after'])
def test_invalid_submission_refuses_and_never_replays(fault):
    ui, status, custom = valid_form()
    ui.run('kiosk-valid-custom-open', '')
    custom.value = 'abc'
    submit = ui.find_id('kiosk-request-submit')
    ui.timeout = .01
    if fault == 'disabled':
        submit.states.discard('sensitive')
    elif fault == 'wrong-child':
        ui.find_id('kiosk-child-selector').children[0].identity = 'kiosk-child-selected-9999'
    elif fault == 'wrong-value':
        custom.value = '1.25'
    elif fault == 'prompt':
        ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
    def submit_once(_):
        if fault == 'uncertain':
            raise RuntimeError('lost reply')
        if fault != 'no-validation':
            status.name = 'Enter a number from 0.1 to 1440 minutes.'
        if fault == 'changed-form':
            custom.value = '0'
        if fault == 'prompt-after':
            ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
        return True
    submit.action.do_action.side_effect = submit_once
    with pytest.raises((UiError, RuntimeError)):
        ui.run('kiosk-invalid-letters-submit', '')
    if fault != 'prompt':  # run's outer prompt guard refuses before entering the operation.
        with pytest.raises(UiError, match='uncertain-input'):
            ui.kiosk_invalid_choice('kiosk-invalid-letters-submit')
    assert submit.action.do_action.call_count == (0 if fault in (
        'disabled', 'wrong-child', 'wrong-value', 'prompt') else 1)


@pytest.mark.parametrize('field,value', [('duration_seconds', 0), ('custom_text', '1.25'),
                                       ('request_enabled', False), ('child', 'existing-fixture-child')])
def test_invalid_decoder_rejects_valid_or_changed_form(field, value):
    ui, _, custom = valid_form()
    ui.run('kiosk-valid-custom-open', '')
    custom.value = 'abc'
    result = ui.run('kiosk-invalid-letters-ready', '')
    result['invalid_choice']['request'][field] = value
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises(EvidenceError):
        observer.observe('kiosk-invalid-letters-ready')


@pytest.mark.parametrize('refusal', [None, 'invalid-wrong-entry', 'kiosk-invalid-empty-submit',
                                  'kiosk-invalid-comma-read'])
def test_invalid_worker_order_text_and_terminal_refusal(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_kiosk_valid_duration').replace(
        "sub record_info { }", "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    worker = worker.replace('    });\n    1;', "    }, 'invalid');\n    1;")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(INVALID_PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])
    if refusal is None:
        assert [event[1] for event in result['events'] if event[0] == 'text'] == [
            '1.25', 'abc', '-1', '0', '0.09', '1440.1', '1,5']


def test_invalid_wrong_entry_refuses_without_input():
    ui = ui_for(Node(identity='parent-window'))
    ui.run('parent-kiosk-invalid-refused', '')


def test_invalid_qualification_reuses_snapshot_and_ledger(tmp_path):
    from parent_setup_qualification import RequestDurationQualification, KioskEntryQualification
    journey = RequestDurationQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is INVALID_PLAN
    assert RequestDurationQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot


@pytest.mark.parametrize('conflict', ['kiosk_valid_duration', 'request_choices', 'allowance'])
def test_invalid_mode_conflicts_refuse_before_vm(conflict):
    import check_graphical_smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='duration-prerequisites'):
        check_graphical_smoke.main(assets='/unused', provision_credentials=True,
                                  request_duration=True, **{conflict: True})


@pytest.mark.parametrize('refusal', [None, 'open-form', 'open-text-selected',
                                  'open-estimate', 'cancel-station-list', 'new-form', 'new-apps'])
def test_flow_worker_order_and_terminal_refusal(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow').replace(
        'sub record_info { }', "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    worker = worker.replace("$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(FLOW_PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])
    if refusal is None:
        assert [event[1] for event in result['events'] if event[0] == 'text'] == ['1.25', '1.25']


@pytest.mark.parametrize('refusal', [None, 'open-estimate', 'cancel-action', 'cancel-returned'])
def test_cancel_case_worker_order_and_terminal_refusal(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_kiosk_cancel').replace(
        'sub record_info { }', "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(CANCEL_PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])
    assert [event[1] for event in result['events'] if event[0] == 'text'] == ['1.25']
    assert expected.count('cancel-action') == 1
    assert expected[-1] == 'cancel-returned'


def test_cancel_case_uses_shared_balance_comparison(tmp_path):
    actions = {}
    journey = KioskValidDurationJourney(SimpleNamespace(directory=tmp_path), Mock(),
                                        CANCEL_PLAN, actions=actions)
    assert journey.plan is CANCEL_PLAN
    assert journey.balance is None
    assert journey.check_settings.__func__ is KioskValidDurationJourney.check_settings


def test_flow_open_uses_supplied_form_and_rejects_unbound_choices():
    stages = prepared_request(prefix='open', entry='open', initial='default', **CHOICES)
    assert not any('station' in stage for stage in stages)
    assert list(stages)[0] == 'open-form'
    for field, value in [('child', 'other-child'), ('duration_seconds', 76), ('allow_soft', False)]:
        with pytest.raises(EvidenceError, match='request-flow:choices'):
            prepared_request(prefix='open', entry='open', initial='default',
                             **{**CHOICES, field: value})


def test_flow_custom_soft_readback_through_controller():
    ui, _, _ = valid_form()
    ui.run('kiosk-valid-custom-open', '')
    observer = UiObservations(Mock())
    for action in ('select', 'read'):
        operation = 'kiosk-valid-fraction-soft-' + action
        result = ui.run(operation, '')
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        assert observer.observe(operation) == result
        assert result['valid_choice']['request']['allow_soft'] is True
        assert result['valid_choice']['request']['duration_seconds'] == 75
    ui.find_id('kiosk-request-submit').action.do_action.assert_not_called()


def test_flow_reselects_approver_with_saved_custom_and_soft_choices():
    ui, _, _ = valid_form()
    ui.run('kiosk-valid-custom-open', '')
    ui.run('kiosk-valid-fraction-soft-select', '')
    result = ui.run('kiosk-flow-approver-select', '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe('kiosk-flow-approver-select') == result
    assert result['valid_choice']['request']['custom_text'] == '1.25'
    assert result['valid_choice']['request']['allow_soft'] is True


@pytest.mark.parametrize('operation', ['kiosk-flow-child-select', 'kiosk-flow-approver-select'])
def test_flow_account_input_refuses_wrong_entry(operation):
    ui = ui_for(Node(identity='parent-window'))
    with pytest.raises(UiError, match='kiosk-account-surface'):
        ui.run(operation, '')


def test_flow_reentry_compares_independent_choices():
    journey = object.__new__(RequestFlowJourney)
    journey.plan = FLOW_PLAN
    journey.balance = {'daily': {'seconds': 900, 'precision_seconds': 1},
                       'one_time': {'seconds': 0, 'precision_seconds': 1},
                       'observed_monotonic_ns': 1_000_000_000}
    journey.prepared = None
    value = {'request': {'duration_seconds': 75, 'allow_soft': True},
             'estimate': {'kind': 'fixed', 'seconds': 975}, 'observed_monotonic_ns': 2_000_000_000}
    journey.check_settings('open-estimate', {'ui': {'valid_choice': value}})
    repeated = {'ui': {'valid_choice': {**value, 'request': dict(value['request'])}}}
    journey.check_settings('new-estimate', repeated)
    assert repeated['comparison']['reproduced_choices']
    repeated['ui']['valid_choice']['request']['allow_soft'] = False
    with pytest.raises(EvidenceError, match='reproduced-choices'):
        journey.check_settings('new-estimate', repeated)


def test_flow_qualification_uses_guarded_snapshot(tmp_path):
    from parent_setup_qualification import RequestFlowQualification, KioskEntryQualification
    journey = RequestFlowQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is FLOW_PLAN
    assert RequestFlowQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
