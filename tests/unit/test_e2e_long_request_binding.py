"""Finite ten-minute request safety; private trees and bounded Perl children only."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import UiError
from kiosk_approved_flow import approved_request, obtain_time
from private_artifacts import EvidenceError
from request_flow import CHOICES, prepared_request
from tests.support.accessible_ui import Node
from tests.support.e2e_kiosk import WORKER, accounts_form
from tests.support.perl import run_perl
from ui_observations import RequestObservation, UiObservations


LONG = {**CHOICES, 'duration_seconds': 600}


def long_form():
    ui, approver, _, _ = accounts_form('approver')
    approver.setValue('1000')
    form = ui.find_id('kiosk-request-form')
    status = Node('Estimated remaining time: 10m', 'label', identity='kiosk-request-status')
    custom = Node('Custom minutes', 'entry', identity='kiosk-custom-duration',
                  states=('visible', 'sensitive', 'editable'), value='')
    for node in (status, custom):
        node.parent = form
        form.children.append(node)
    custom.get_text_iface = lambda: SimpleNamespace(
        get_character_count=lambda: len(custom.value),
        get_text=lambda start, end: custom.value[start:end])
    ui.api.Text = SimpleNamespace(get_character_count=lambda iface: iface.get_character_count(),
                                 get_text=lambda iface, start, end: iface.get_text(start, end))
    def select(_):
        for node in form.children:
            if node.identity.startswith('kiosk-duration-'):
                node.states.discard('pressed')
        ui.find_id('kiosk-duration-custom').states.add('pressed')
        custom.states.add('showing')
        return True
    ui.find_id('kiosk-duration-custom').action.do_action.side_effect = select
    return ui, status, custom


def long_prompt():
    ui, status, custom = long_form()
    ui.kiosk_valid_choice('kiosk-long-request-duration-select')
    ui.kiosk_valid_choice('kiosk-long-request-soft-select')
    desktop = Node('desktop', 'desktop frame', children=[ui.root()])
    ui.api.get_desktop = lambda _: desktop
    field = Node(role='password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.length = 0
    field.get_text_iface = lambda: SimpleNamespace(
        get_character_count=lambda: field.length,
        get_text=Mock(side_effect=AssertionError('protected password contents')))
    field.get_description = Mock(side_effect=AssertionError('protected description'))
    field.get_child_count = Mock(side_effect=AssertionError('protected children'))
    message = Node(f'Grant {accessible_ui.CHILD} access?\nRequested time: 10 minutes.\n'
                   'Allow soft blocked apps for this grant.', 'label')
    recipient = Node('Password for onpc-parent-jamie:', 'label')
    authenticate = Node('Authenticate', 'push button')
    dialog = Node('Authenticate', 'dialog', children=[message, recipient, field,
                  Node('Cancel', 'push button'), authenticate])
    agent = Node('mate-polkit', 'application', children=[dialog])
    agent.parent = desktop
    submit = ui.find_id('kiosk-request-submit')
    submit.action.do_action.side_effect = lambda _: desktop.children.append(agent) or True
    ui.mate_agent_pid = Mock(return_value=100)
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    ui.kiosk_approval_success = Mock(return_value={'approved': True, 'form_success': True})
    return ui, message, recipient, field, submit, authenticate


def test_long_composition_is_explicit_and_keeps_old_defaults():
    assert CHOICES['duration_seconds'] == 75
    assert prepared_request(prefix='open', entry='open', initial='default', **CHOICES)[
        'open-estimate'] == 'ui:kiosk-valid-fraction-soft-read'
    flow = obtain_time(initial='default', **LONG, exit='automatic')
    assert flow['new-duration'] == 'ui:kiosk-long-request-duration-select'
    assert flow['new-estimate'] == 'ui:kiosk-long-request-soft-read'
    assert [op for op in flow.values() if op.startswith('ui:kiosk-long-mate-')] == [
        'ui:' + op for op in accessible_ui.LONG_MATE_ORDER]
    assert not any('text-' in stage for stage in flow)


@pytest.mark.parametrize('change', [{'duration_seconds': 601}, {'duration_seconds': 600.0},
                                  {'duration_seconds': True}, {'child': 'other-fixture-child'},
                                  {'approver': 'other-fixture-parent'}, {'allow_soft': False}])
def test_long_flow_rejects_unqualified_request_before_operations(change):
    with pytest.raises(EvidenceError, match='choices'):
        obtain_time(initial='default', **{**LONG, **change}, exit='automatic')


@pytest.mark.parametrize('change', [{'initial': 'selected'}, {'surface': 'overlay'}])
def test_long_prepare_refuses_unqualified_surface_or_retained_state(change):
    with pytest.raises(EvidenceError, match='long-'):
        prepared_request(**{'prefix': 'open', 'entry': 'open', 'initial': 'default',
                            **LONG, **change})


def test_long_approval_refuses_immediate_exit():
    with pytest.raises(EvidenceError, match='long-exit'):
        approved_request(**LONG, exit='immediate')


def test_long_product_choices_use_exact_custom_value_and_decode_independently():
    ui, _, custom = long_form()
    for operation in ('kiosk-long-request-duration-select', 'kiosk-long-request-duration-read',
                      'kiosk-long-request-soft-select', 'kiosk-long-request-soft-read'):
        result = ui.run(operation, '')
        observer = UiObservations(Mock())
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        assert observer.observe(operation) == result
        assert result['valid_choice']['request']['duration_seconds'] == 600
        assert result['valid_choice']['request']['custom_text'] == '10'
    custom.setText.assert_called_once_with('10')
    with pytest.raises(EvidenceError, match='ui:request'):
        RequestObservation.from_request(result['valid_choice']['request'],
                                        operation='kiosk-valid-fraction-soft-read')


@pytest.mark.parametrize('fault', [None, 'duration', 'child', 'approver', 'apps', 'duplicate'])
def test_long_native_prompt_checks_exact_binding_before_recipient_proof(fault):
    ui, message, recipient, field, submit, authenticate = long_prompt()
    if fault == 'duration': message.name = message.name.replace('10 minutes', '1 minute, 15 seconds')
    if fault == 'child': message.name = message.name.replace(accessible_ui.CHILD, 'Jordan')
    if fault == 'approver': recipient.name = 'Password for onpc-parent-casey:'
    if fault == 'apps': message.name = message.name.split('\nAllow')[0]
    if fault == 'duplicate':
        duplicate = Node(message.name, 'label')
        duplicate.parent = message.parent
        message.parent.children.append(duplicate)
    if fault:
        with pytest.raises(UiError, match='context-missing'):
            ui.run('kiosk-long-mate-open', '')
        ui.mate_challenge_identity.assert_not_called()
        with pytest.raises(UiError, match='uncertain-input'):
            ui.run('kiosk-long-mate-open', '')
    else:
        assert ui.run('kiosk-long-mate-open', '')['approval'] == {
            'challenge_id': 'a' * 64, 'request': LONG}
    submit.action.do_action.assert_called_once()
    authenticate.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called()
    field.get_description.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'changed-before-filled', 'replacement'])
def test_long_native_request_binding_survives_every_recipient_and_filled_recheck(fault):
    ui, message, _, field, _, authenticate = long_prompt()
    observer = UiObservations(Mock())
    def observe(_args, operation, **_kwargs):
        ui.expected_mate_challenge = getattr(observer, 'mate_approval_identity', None)
        result = ui.run(operation, '')
        if operation != accessible_ui.LONG_MATE_ORDER[0]:
            result['boot_sha256'] = 'c' * 64
        return json.dumps(result).encode(), []
    observer.call = Mock(side_effect=observe)
    for operation in accessible_ui.LONG_MATE_ORDER[:-1]:
        assert observer.observe(operation)['approval']['request'] == LONG
    field.length = 8
    if fault == 'changed-before-filled':
        message.name = message.name.replace('10 minutes', '1 minute, 15 seconds')
    if fault == 'replacement': ui.mate_challenge_identity.return_value = 'b' * 64
    if fault:
        with pytest.raises(UiError, match='context-missing|replacement'):
            observer.observe(accessible_ui.LONG_MATE_ORDER[-1])
        authenticate.action.do_action.assert_not_called()
    else:
        assert observer.observe(accessible_ui.LONG_MATE_ORDER[-1])['approval'] == {
            'approved': True, 'form_success': True}
        authenticate.action.do_action.assert_called_once()
        ui.kiosk_approval_success.assert_called_once_with(immediate=False)


@pytest.mark.parametrize('fault', ['order', 'request', 'identity'])
def test_long_controller_refuses_crossed_order_request_or_challenge(fault):
    observer = UiObservations(Mock())
    result = {'operation': 'kiosk-long-mate-open', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider', 'approval': {
        'challenge_id': 'a' * 64, 'request': dict(LONG)}}
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    observer.observe(result['operation'])
    operation = 'kiosk-mate-qualified' if fault == 'order' else 'kiosk-long-mate-qualified'
    result['operation'] = operation
    result['boot_sha256'] = 'c' * 64
    if fault == 'request': result['approval']['request']['duration_seconds'] = 75
    if fault == 'identity': result['approval']['challenge_id'] = 'b' * 64
    observer.call.return_value = json.dumps(result).encode(), []
    with pytest.raises(EvidenceError, match='mate-order|request-binding|replacement'):
        observer.observe(operation)
    assert observer.call.call_count == (1 if fault == 'order' else 2)


LONG_WORKER = WORKER.partition('require onpc_kiosk_eligible_choices;')[0] + r'''
require onpc_request_flow;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'baseline-app-effects', review => 0, exchange => sub {
    my ($stage) = @_;
    push @events, ['stage', $stage];
    die 'fixture:refused' if ($ENV{ONPC_TEST_REFUSE_STAGE} // '') eq $stage;
    return {observed => $stage, ui_focused => JSON::PP::true}
        if $stage =~ /(?:station-list|focused)\z/;
    return {observed => $stage, station_destination => 'default-request-form'}
        if $stage =~ /station-branch\z/;
    return {observed => $stage};
});
my $ok = eval {
    onpc_request_flow::obtain_time($journey, 'default', 'fixture-child', 'fixture-parent', 600, 1, 'automatic');
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''


@pytest.mark.parametrize('refusal', [None, 'new-duration', 'new-estimate', 'approval-open',
                                   'approval-qualified', 'approval-rechecked', 'approval-success'])
def test_long_worker_consumes_ordered_leaves_and_stops_before_secret_on_refusal(monkeypatch, refusal):
    if refusal: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(LONG_WORKER).stdout)
    expected = list(obtain_time(initial='default', **LONG, exit='automatic'))
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == (expected[:expected.index(refusal) + 1] if refusal else expected)
    assert bool(result['ok']) is (refusal is None), result['error']
    assert sum(event[0] == 'secret' for event in result['events']) == (
        1 if refusal in (None, 'approval-success') else 0)


def test_long_worker_refuses_wrong_caller_and_replayed_approval_before_another_secret():
    wrong = LONG_WORKER.replace("prefix => 'baseline-app-effects'", "prefix => 'kiosk-approval'")
    result = json.loads(run_perl(wrong).stdout)
    assert not result['ok'] and 'secret:input-failed' in result['error']
    assert not any(event[0] == 'secret' for event in result['events'])
    repeated = LONG_WORKER.replace("    1;\n};", "    onpc_password::enter_kiosk_mate_password($journey, 'long-request');\n    1;\n};")
    result = json.loads(run_perl(repeated).stdout)
    assert not result['ok'] and 'secret:input-failed' in result['error']
    assert sum(event[0] == 'secret' for event in result['events']) == 1
