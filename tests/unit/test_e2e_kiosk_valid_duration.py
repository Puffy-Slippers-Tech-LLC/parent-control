"""Valid kiosk choices: private tree doubles and bounded Perl child only.

No shared files, buses, displays, sockets or fixture builds; unit-compatible.
"""
import json
import sys
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
from kiosk_escape import PLAN as ESCAPE_PLAN
from mate_prompt import PLAN as MATE_PLAN
from kiosk_approval import PLAN as APPROVAL_PLAN
from auth_result import PLAN as AUTH_RESULT_PLAN
from kiosk_approved_flow import PLAN as APPROVED_FLOW_PLAN, approved_request, obtain_time
from kiosk_rejection import PLAN as REJECTION_PLAN, KioskRejectionJourney
from restricted_station import PLAN as STATION_PLAN


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


@pytest.mark.parametrize('fault', [None, 'terminal', 'shell', 'management',
                                  'control', 'incomplete', 'stale', 'wrong-owner', 'duplicate'])
def test_station_restrictions_inspect_complete_public_tree(fault):
    from tests.support.e2e_kiosk import request_form
    ui, _ = request_form()
    ui.timeout = 3
    app = ui.root()
    desktop = Node(children=[app])
    ui.api.get_desktop = lambda _: desktop
    if fault in ('terminal', 'shell', 'management'):
        # No provider name/role/ID is needed to detect forbidden public content.
        desktop.children.append(Node(children=[Node()]))
    elif fault == 'control':
        ui.find_id('kiosk-request-form').children.append(
            Node('Settings', 'push button', identity='kiosk-settings-launch'))
    elif fault == 'incomplete':
        desktop.children.append(None)
    elif fault == 'stale':
        ui.find_id('kiosk-request-form').states.add('defunct')
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    elif fault == 'duplicate':
        app.children.append(Node(identity='kiosk-request-form'))
    if fault:
        with pytest.raises(UiError):
            ui.kiosk_restrictions(stable_seconds=0)
    else:
        result = ui.run('kiosk-restriction-read', '')
        observer = UiObservations(Mock())
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        assert observer.observe('kiosk-restriction-read') == result


def test_station_shortcut_ready_focuses_owned_cancel_without_activating_it():
    from tests.support.e2e_kiosk import request_form
    ui, _ = request_form()
    window = ui.find_id('kiosk-request-window')
    cancel = ui.find_id('kiosk-request-cancel')
    window.action.get_action_name = lambda _: 'focus.kiosk-request-cancel'
    window.action.do_action.side_effect = lambda _: cancel.states.add('focused') or True
    ui.run('kiosk-restriction-ready', '')
    assert 'focused' in cancel.states
    cancel.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'named-toggle', 'extra-toggle', 'outside-menu',
                                  'nested-control', 'wrong-menu-id'])
def test_station_menu_toolkit_toggle_is_not_a_separate_product_action(fault):
    from tests.support.e2e_kiosk import request_form
    ui, _ = request_form()
    window = ui.find_id('kiosk-request-window')
    toggle = Node(role='toggle button')
    menu = Node(role='button', identity='kiosk-menu-button', children=[toggle])
    window.children.append(menu)
    if fault == 'named-toggle':
        toggle.identity = 'kiosk-settings-launch'
    elif fault == 'extra-toggle':
        menu.children.append(Node(role='toggle button'))
    elif fault == 'outside-menu':
        menu.children.remove(toggle)
        window.children.append(toggle)
    elif fault == 'nested-control':
        toggle.children.append(Node(role='push button'))
    elif fault == 'wrong-menu-id':
        menu.identity = 'kiosk-settings-menu'
    if fault:
        with pytest.raises(UiError, match='ui:station-forbidden-control'):
            ui.kiosk_restrictions(stable_seconds=0)
    else:
        assert ui.kiosk_restrictions(stable_seconds=0)
    toggle.action.do_action.assert_not_called()


@pytest.mark.parametrize('refusal', [None, 'restriction-overview-ready',
                                   'restriction-grid-read', 'restriction-terminal-read',
                                   'approval-qualified', 'approval-success', 'new-returned'])
def test_restricted_station_worker_order_and_refusal(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_restricted_station').replace(
        'sub record_info { }', "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(STATION_PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])
    if refusal is None:
        keys = [event[1] for event in result['events'] if event[0] == 'key']
        assert [key for key in keys if key in ('super', 'super-a', 'ctrl-alt-t')] == [
            'super', 'super-a', 'ctrl-alt-t']
        assert sum(event[0] == 'secret' for event in result['events']) == 2
    elif refusal.startswith('restriction-'):
        assert not any(event[0] == 'text' for event in result['events'])


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


@pytest.mark.parametrize('refusal', [None, 'open-estimate', 'escape-ready', 'escape-returned'])
def test_escape_case_worker_order_single_input_and_terminal_refusal(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_kiosk_escape').replace(
        'sub record_info { }', "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(ESCAPE_PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])
    assert [event[1] for event in result['events'] if event[0] == 'text'] == ['1.25']
    escapes = [index for index, event in enumerate(result['events']) if event == ['key', 'esc']]
    assert len(escapes) == (0 if refusal in ('open-estimate', 'escape-ready') else 1)
    if escapes:
        index = escapes[0]
        assert result['events'][index - 1:index + 2] == [
            ['stage', 'escape-ready'], ['key', 'esc'], ['stage', 'escape-returned']]
    if refusal:
        assert result['events'][-1] == ['stage', refusal]


@pytest.mark.parametrize('plan', [CANCEL_PLAN, ESCAPE_PLAN])
def test_exit_case_uses_shared_balance_comparison(tmp_path, plan):
    actions = {}
    journey = KioskValidDurationJourney(SimpleNamespace(directory=tmp_path), Mock(),
                                        plan, actions=actions)
    assert journey.plan is plan
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


def mate_form():
    """Private public-tree double; no service, files, secret or display access."""
    ui, status, custom = valid_form()
    ui.kiosk_valid_choice('kiosk-valid-custom-open')
    ui.kiosk_valid_choice('kiosk-valid-fraction-soft-select')
    app = ui.root()
    desktop = Node('desktop', 'desktop frame', children=[app])
    ui.api.get_desktop = lambda _: desktop
    field = Node(role='password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: SimpleNamespace(
        get_character_count=lambda: 0, get_text=Mock(side_effect=AssertionError('password content')))
    # Public accessible names are labels; never traverse or read secret contents.
    field.get_description = Mock(side_effect=AssertionError('protected description'))
    field.get_child_count = Mock(side_effect=AssertionError('protected children'))
    cancel = Node('Cancel', 'push button')
    message = Node(f'Grant {accessible_ui.CHILD} 1 minute, 15 seconds and allow soft blocked apps?', 'label')
    recipient = Node('Password for onpc-parent-jamie:', 'label')
    dialog = Node('Authenticate', 'dialog', children=[message, recipient, field, cancel])
    agent = Node('mate-polkit', 'application', children=[dialog])
    agent.parent = desktop
    submit = ui.find_id('kiosk-request-submit')
    submit.action.do_action.side_effect = lambda _: desktop.children.append(agent) or True
    cancel.action.do_action.side_effect = lambda _: desktop.children.remove(agent) or True
    ui.mate_agent_pid = Mock(return_value=100)
    ui.mate_provider_metadata = Mock(return_value={
        'version': '1.26.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]})
    return ui, desktop, agent, dialog, field, cancel, submit, message, recipient


@pytest.mark.parametrize('sources', [[], [('xkb', 'gb')]])
def test_mate_metadata_uses_kiosk_keyboard_configuration(monkeypatch, sources):
    ui = ui_for(Node())
    path = Mock(return_value=SimpleNamespace(read_bytes=lambda:
        b'LANG=de_DE.UTF-8\0LC_MESSAGES=en_US.UTF-8\0'))
    monkeypatch.setattr(accessible_ui, 'Path', path)
    monkeypatch.setenv('LC_ALL', 'fr_FR.UTF-8')
    query = Mock(return_value='1.26.1-1build3\n')
    monkeypatch.setattr(accessible_ui.subprocess, 'check_output', query)
    settings = Mock()
    settings.get_value.return_value.unpack.return_value = sources
    gio = SimpleNamespace(Settings=SimpleNamespace(new=Mock(return_value=settings)))
    monkeypatch.setitem(sys.modules, 'gi.repository', SimpleNamespace(Gio=gio))
    system_sources = Mock(return_value=[['xkb', 'us']])
    monkeypatch.setattr(accessible_ui, 'greeter_keyboard_sources', system_sources)
    result = ui.mate_provider_metadata(4321)
    assert result == {'version': '1.26.1-1build3', 'locale': 'en_US.UTF-8',
                      'keyboard': [['xkb', 'gb']] if sources else [['xkb', 'us']]}
    path.assert_called_once_with('/proc/4321/environ')
    query.assert_called_once_with(
        ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', 'mate-polkit'],
        text=True, timeout=5)
    gio.Settings.new.assert_called_once_with('org.gnome.desktop.input-sources')
    settings.get_value.assert_called_once_with('sources')
    if sources:
        system_sources.assert_not_called()
    else:
        system_sources.assert_called_once_with()
        system_sources.side_effect = RuntimeError('locale1 unavailable')
        with pytest.raises(RuntimeError, match='locale1 unavailable'):
            ui.mate_provider_metadata(4321)


@pytest.mark.parametrize('operation', sorted(accessible_ui.MATE_OPERATIONS))
def test_mate_cancel_real_decoder_single_input_and_unchanged_form(operation):
    ui, desktop, agent, _dialog, field, cancel, submit, *_ = mate_form()
    result = ui.run(operation, '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe(operation) == result
    assert agent not in desktop.children
    submit.action.do_action.assert_called_once()
    cancel.action.do_action.assert_called_once()
    field.get_child_count.assert_not_called()
    assert result['mate']['refusals'] is (operation == 'kiosk-mate-refusals-cancel')
    assert result['mate']['rejected_proofs'] == (list(accessible_ui.MATE_REFUSALS)
        if operation == 'kiosk-mate-refusals-cancel' else [])
    assert result['mate']['same_challenge_rechecked'] is True
    with pytest.raises(Exception, match='ui:challenge-replay'):
        observer.observe(operation)
    assert 'onpc-parent-jamie' not in json.dumps(result)


@pytest.mark.parametrize('fault', ['agent', 'owner', 'duplicate-owner', 'duplicate-field',
                                  'hidden', 'disabled', 'focus', 'nonempty', 'recipient',
                                  'context', 'cancel', 'incomplete', 'stale'])
def test_mate_prompt_refuses_before_cancel_and_latches_failure(fault):
    ui, desktop, agent, dialog, field, cancel, submit, message, recipient = mate_form()
    if fault == 'agent':
        agent.name = 'gnome-shell'
    elif fault == 'owner':
        agent.get_process_id = lambda: 999
    elif fault == 'duplicate-owner':
        desktop.children.append(Node('mate-polkit', 'application'))
    elif fault == 'duplicate-field':
        dialog.children.append(Node(role='password text'))
    elif fault in ('hidden', 'disabled', 'focus'):
        field.states.discard({'hidden': 'visible', 'disabled': 'sensitive', 'focus': 'focused'}[fault])
    elif fault == 'nonempty':
        field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 1)
    elif fault == 'recipient':
        recipient.name = 'Password for onpc-parent-casey:'
    elif fault == 'context':
        message.name = 'Authentication is required'
    elif fault == 'cancel':
        cancel.states.discard('sensitive')
    elif fault == 'incomplete':
        dialog.children.append(None)
    else:
        field.states.add('defunct')
    with pytest.raises(UiError):
        ui.run('kiosk-mate-cancel', '')
    cancel.action.do_action.assert_not_called()
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-mate-cancel', '')
    submit.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['replacement', 'service-replaced', 'uncertain', 'unchanged',
                                  'form-changed', 'error'])
def test_mate_cancel_replacement_or_uncertain_result_never_replays(fault):
    ui, desktop, agent, dialog, field, cancel, submit, *_ = mate_form()
    if fault == 'replacement':
        def metadata(_pid):
            replacement = Node('Cancel', 'push button')
            replacement.parent = dialog
            dialog.children[-1] = replacement
            return {'version': '1', 'locale': 'C', 'keyboard': [['xkb', 'us']]}
        ui.mate_provider_metadata.side_effect = metadata
    elif fault == 'service-replaced':
        ui.mate_agent_pid.side_effect = [100, 999]
    elif fault == 'uncertain':
        cancel.action.do_action.side_effect = RuntimeError('lost response')
    elif fault == 'unchanged':
        cancel.action.do_action.side_effect = None
    else:
        def dismiss(_):
            desktop.children.remove(agent)
            if fault == 'form-changed':
                ui.find_id('kiosk-soft-apps-toggle').states.discard('checked')
            else:
                ui.find_id('kiosk-request-status').name = 'Request denied'
            return True
        cancel.action.do_action.side_effect = dismiss
    with pytest.raises((UiError, RuntimeError),
                       match='ui:kiosk-estimate:request-denied' if fault == 'error' else None):
        ui.run('kiosk-mate-cancel', '')
    with pytest.raises(UiError, match='uncertain-input'):
        ui.run('kiosk-mate-cancel', '')
    submit.action.do_action.assert_called_once()
    assert cancel.action.do_action.call_count == (0 if fault in ('replacement', 'service-replaced') else 1)


@pytest.mark.parametrize('refusal', [None, 'mate-wrong-entry', 'kiosk-invalid-letters-submit',
                                   'open-mate', 'new-mate'])
def test_mate_worker_uses_independent_entries_and_stops_on_refusal(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow').replace(
        'sub record_info { }', "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    worker = worker.replace("$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")
    worker = worker.replace('    });', "    }, 'mate');")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(MATE_PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])


def test_mate_qualification_uses_guarded_snapshot(tmp_path):
    from parent_setup_qualification import MatePromptQualification, KioskEntryQualification
    journey = MatePromptQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is MATE_PLAN
    assert MatePromptQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot


@pytest.mark.parametrize('fault', ['recipient', 'child', 'duration', 'apps', 'field', 'proofs', 'id'])
def test_auth_prompt_controller_rejects_incomplete_or_wrong_proof(fault):
    ui, *_ = mate_form()
    result = ui.run('kiosk-mate-refusals-cancel', '')
    key, value = {
        'recipient': ('approver', 'other-parent'), 'child': ('child', 'other-child'),
        'duration': ('duration_seconds', 300), 'apps': ('allow_soft', False),
        'field': ('same_challenge_rechecked', False), 'proofs': ('rejected_proofs', []),
        'id': ('challenge_id', ''),
    }[fault]
    result['mate'][key] = value
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises(Exception, match='ui:'):
        observer.observe('kiosk-mate-refusals-cancel')


@pytest.mark.parametrize('conflict', ['request_flow', 'request_duration', 'kiosk_valid_duration',
                                   'request_choices', 'allowance'])
def test_mate_qualification_refuses_conflicting_modes(conflict):
    import check_graphical_smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='prerequisites'):
        check_graphical_smoke.main(assets='/not-used', provision_credentials=True,
                                  mate_prompt=True, **{conflict: True})


@pytest.mark.parametrize('refusal', [None, 'approval-open', 'approval-qualified',
                                   'approval-rechecked', 'approval-success', 'new-returned'])
@pytest.mark.parametrize('binding', ['approval', 'rejection', 'immediate', 'approved-flow'])
def test_approval_worker_order_and_secret_once(monkeypatch, refusal, binding):
    if refusal and binding == 'rejection':
        refusal = refusal.replace('approval-', 'rejection-').replace('rejection-success', 'rejection-result')
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow').replace(
        'sub record_info { }', "sub record_info { }\nsub type_string { push @main::events, ['text', $_[0]] }")
    worker = worker.replace("$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")
    worker = worker.replace('    });', "    }, '" + binding + "');")
    result = json.loads(run_perl(worker).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list({'approval': APPROVAL_PLAN, 'rejection': REJECTION_PLAN,
                     'immediate': AUTH_RESULT_PLAN, 'approved-flow': APPROVED_FLOW_PLAN}[binding].screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert stages == (expected if refusal is None else expected[:expected.index(refusal) + 1])
    assert sum(event[0] == 'secret' for event in result['events']) == (
        1 if refusal in tuple(('rejection' if binding == 'rejection' else 'approval') + '-' + item
                              for item in ('open', 'qualified', 'rechecked')) else 2)


@pytest.mark.parametrize('changed', [{'child': 'other-child'}, {'approver': 'other-parent'},
                                   {'duration_seconds': 300}, {'allow_soft': False},
                                   {'exit': 'immediate'}])
def test_approved_composites_refuse_unsupported_bindings(changed):
    choices = {**CHOICES, 'exit': 'automatic', **changed}
    for flow, extra in ((approved_request, {}), (obtain_time, {'initial': 'selected'})):
        with pytest.raises(Exception, match='approved-flow:'):
            flow(**choices, **extra)


def test_approved_flow_composes_leaves_and_owned_snapshot(tmp_path):
    from parent_setup_qualification import KioskApprovedFlowQualification, KioskEntryQualification
    assert list(APPROVED_FLOW_PLAN.screen_tags.items()) == list(APPROVAL_PLAN.screen_tags.items())
    assert approved_request(**CHOICES, exit='automatic')['new-returned'] == 'ui:gdm-station-returned'
    journey = KioskApprovedFlowQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is APPROVED_FLOW_PLAN
    assert KioskApprovedFlowQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot


@pytest.mark.parametrize('fault', [None, 'changed', 'nonempty', 'unfocused', 'uncertain'])
def test_approval_proofs_preserve_recipient_and_challenge(fault):
    ui, desktop, agent, dialog, field, cancel, submit, *_ = mate_form()
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    assert ui.run('kiosk-mate-open', '')['approval'] == {'challenge_id': 'a' * 64}
    ui.expected_mate_challenge = 'a' * 64
    if fault == 'changed':
        ui.mate_challenge_identity.return_value = 'b' * 64
    elif fault == 'nonempty':
        field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 1)
    elif fault == 'unfocused':
        field.states.discard('focused')
    elif fault == 'uncertain':
        ui.input_uncertain = True
    if fault:
        with pytest.raises(UiError):
            ui.run('kiosk-mate-qualified', '')
    else:
        assert ui.run('kiosk-mate-qualified', '')['approval'] == {'challenge_id': 'a' * 64}
        assert ui.run('kiosk-mate-rechecked', '')['approval'] == {'challenge_id': 'a' * 64}
    submit.action.do_action.assert_called_once()
    cancel.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'replacement', 'empty', 'uncertain', 'denied'])
@pytest.mark.parametrize('immediate', [False, True])
def test_approval_submits_once_and_requires_explicit_success(fault, immediate):
    ui, desktop, agent, dialog, field, cancel, submit, *_ = mate_form()
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    ui.run('kiosk-mate-open', '')
    ui.expected_mate_challenge = 'b' * 64 if fault == 'replacement' else 'a' * 64
    field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 0 if fault == 'empty' else 5)
    authenticate = Node('Authenticate', 'push button')
    authenticate.parent = dialog
    dialog.children.append(authenticate)
    window = ui.find_id('kiosk-request-window')
    result = Node(identity='kiosk-result-page', children=[Node(
        'Request denied' if fault == 'denied' else 'Request approved', 'label', identity='kiosk-result-title')])
    result.parent = window
    exit_action = Node('Return to Login (3)', 'push button', identity='kiosk-result-action')
    exit_action.parent = result
    result.children.append(exit_action)
    operation = 'kiosk-mate-submit-immediate' if immediate else 'kiosk-mate-submit-success'
    def approve(_):
        desktop.children.remove(agent)
        window.children.append(result)
        return True
    authenticate.action.do_action.side_effect = approve
    if fault == 'uncertain':
        authenticate.action.do_action.side_effect = RuntimeError('private failure')
    if fault:
        with pytest.raises((UiError, RuntimeError)):
            ui.run(operation, '')
        with pytest.raises(UiError, match='uncertain'):
            ui.run(operation, '')
    else:
        assert ui.run(operation, '')['approval'] == {
            'approved': True, 'form_success': True, **({'immediate_exit': True} if immediate else {})}
    assert authenticate.action.do_action.call_count == (0 if fault in ('replacement', 'empty') else 1)
    assert exit_action.action.do_action.call_count == (1 if immediate and not fault else 0)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'hidden', 'disabled', 'uncertain'])
def test_immediate_exit_refuses_unusable_action_and_never_replays(fault):
    ui, desktop, agent, dialog, *_ = mate_form()
    window = ui.find_id('kiosk-request-window')
    action = Node('Return to Login (3)', 'push button', identity='kiosk-result-action')
    page = Node(identity='kiosk-result-page', children=[
        Node('Request approved', 'label', identity='kiosk-result-title'), action])
    page.parent = window
    window.children.append(page)
    if fault == 'missing':
        page.children.remove(action)
    elif fault == 'duplicate':
        other = Node(identity='kiosk-result-action')
        other.parent = page
        page.children.append(other)
    elif fault in ('hidden', 'disabled'):
        action.states.discard('visible' if fault == 'hidden' else 'sensitive')
    else:
        action.action.do_action.side_effect = RuntimeError('uncertain exit')
    with pytest.raises((UiError, RuntimeError)):
        ui.kiosk_approval_success(immediate=True)
    assert action.action.do_action.call_count == (1 if fault == 'uncertain' else 0)
    if fault == 'uncertain':
        with pytest.raises(UiError, match='uncertain'):
            ui.kiosk_approval_success(immediate=True)
        assert action.action.do_action.call_count == 1


@pytest.mark.parametrize('fault', [None, 'replay', 'changed', 'intervening', 'out-of-order', 'stale'])
@pytest.mark.parametrize('binding', ['approval', 'rejection', 'immediate'])
def test_approval_controller_reconciles_fresh_proofs_and_latches(fault, binding):
    observer = UiObservations(Mock())
    operations = (('kiosk-mate-open', 'kiosk-mate-qualified', 'kiosk-mate-rechecked',
                   'kiosk-mate-submit-immediate' if binding == 'immediate' else 'kiosk-mate-submit-success')
                  if binding != 'rejection' else accessible_ui.MATE_REJECTION_ORDER)
    def call(_args, operation, **_kwargs):
        approval = ({'approved': True, 'form_success': True, 'immediate_exit': True}
                    if operation.endswith('immediate') else
                    {'approved': True, 'form_success': True} if operation.endswith('success') else
                    {'rejected': True, 'cancelled': True, 'no_error': True} if operation.endswith('submit-rejection') else
                    {'challenge_id': ('b' if fault == 'changed' and operation.endswith('rechecked') else 'a') * 64})
        value = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'approval': approval}
        if operation != operations[0]:
            value['boot_sha256'] = 'c' * 64
        return json.dumps(value).encode(), []
    observer.call = Mock(side_effect=call)
    observer.observe(operations[0])
    if fault == 'stale':
        observer.mate_approval_checked = float('-inf')
    if fault:
        operation = {'replay': operations[0], 'intervening': 'desktop',
                     'out-of-order': operations[3], 'changed': operations[2],
                     'stale': operations[1]}[fault]
        if fault == 'changed':
            observer.observe(operations[1])
        with pytest.raises(Exception, match='ui:'):
            observer.observe(operation)
        with pytest.raises(Exception, match='ui:'):
            observer.observe(operations[1])
    else:
        for operation in operations[1:]:
            observer.observe(operation)


@pytest.mark.parametrize('fault', [None, 'missing-rejection', 'disappeared', 'wrong-owner',
                                  'duplicate-rejection', 'uncertain-cancel', 'changed-form'])
def test_rejection_requires_explicit_message_then_one_cancel_and_public_form(fault):
    ui, desktop, agent, dialog, field, cancel, submit, *_ = mate_form()
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    observer = UiObservations(Mock())
    def call(_args, operation, **_kwargs):
        ui.expected_mate_challenge = getattr(observer, 'mate_approval_identity', None)
        result = ui.run(operation, '')
        if operation != accessible_ui.MATE_REJECTION_ORDER[0]:
            result['boot_sha256'] = 'c' * 64
        return json.dumps(result).encode(), []
    observer.call = Mock(side_effect=call)
    for operation in accessible_ui.MATE_REJECTION_ORDER[:3]:
        observer.observe(operation)
    field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 5)
    authenticate = Node('Authenticate', 'push button')
    authenticate.parent = dialog
    dialog.children.append(authenticate)
    def reject(_):
        field.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: 0)
        if fault == 'disappeared':
            desktop.children.remove(agent)
        elif fault != 'missing-rejection':
            for _ in range(2 if fault == 'duplicate-rejection' else 1):
                label = Node('Your authentication attempt was unsuccessful. Please try again.', 'label')
                label.parent = dialog
                dialog.children.append(label)
        if fault == 'wrong-owner':
            agent.get_process_id = lambda: 999
        if fault == 'changed-form':
            ui.find_id('kiosk-soft-apps-toggle').states.discard('checked')
        return True
    authenticate.action.do_action.side_effect = reject
    if fault == 'uncertain-cancel':
        cancel.action.do_action.side_effect = RuntimeError('private failure')
    if fault:
        with pytest.raises((UiError, RuntimeError)):
            observer.observe(accessible_ui.MATE_REJECTION_ORDER[3])
    else:
        assert observer.observe(accessible_ui.MATE_REJECTION_ORDER[3])['approval'] == {
            'rejected': True, 'cancelled': True, 'no_error': True}
    with pytest.raises(Exception, match='ui:'):
        observer.observe(accessible_ui.MATE_REJECTION_ORDER[3])
    authenticate.action.do_action.assert_called_once()
    assert cancel.action.do_action.call_count == (1 if fault in (None, 'uncertain-cancel', 'changed-form') else 0)
    field.get_child_count.assert_not_called()


def test_rejection_plan_independent_form_comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(RequestFlowJourney, 'check_settings', lambda *_: None)
    journey = KioskRejectionJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.prepared = {'choice': 'before'}
    observed = {'ui': {'valid_choice': {'request': {'choice': 'after'}}}, 'comparison': {}}
    with pytest.raises(EvidenceError, match='changed-form'):
        journey.check_settings('rejection-form', observed)
    observed['ui']['valid_choice']['request'] = journey.prepared.copy()
    journey.check_settings('rejection-form', observed)
    assert observed['comparison'] == {'preserved_choices': True}


def test_approval_qualification_uses_guarded_snapshot(tmp_path):
    from parent_setup_qualification import KioskApprovalQualification, KioskEntryQualification
    journey = KioskApprovalQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is APPROVAL_PLAN
    assert KioskApprovalQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot


def test_immediate_qualification_uses_guarded_snapshot(tmp_path):
    from parent_setup_qualification import AuthResultQualification, KioskEntryQualification
    journey = AuthResultQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is AUTH_RESULT_PLAN
    assert AuthResultQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
