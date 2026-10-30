"""Shell AUTH01 context, protected input, decoder and independent attempt guards.

Parallelism: in-memory trees/doubles and private tmp_path, no live VM/display.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as a
from approval_return import ApprovalReturnJourney
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from ui_observations import UiObservations


def prompt(monkeypatch):
    field = Node(role='password text', states=('visible', 'showing', 'sensitive', 'focused'))
    field.length = 0
    field.get_text_iface = Mock(side_effect=lambda: SimpleNamespace(get_character_count=lambda: field.length))
    field.get_description = Mock(side_effect=AssertionError('protected description'))
    field.get_child_count = Mock(side_effect=AssertionError('protected children'))
    cancel = Node('Cancel', 'push button')
    # Shell has no Action interface: only its normal Escape binding is used.
    cancel.get_action_iface = Mock(return_value=None)
    recipient = Node(a.PARENT, 'label')
    message = Node(f'Grant access to {a.CHILD}\nfor 1 minute, 15 seconds\n\n'
                   '✓ Soft-blocked apps allowed', 'label')
    dialog = Node('Authentication Required', 'dialog', children=[recipient, message, field, cancel])
    owner = Node('gnome-shell', 'application', children=[dialog])
    desktop = Node('desktop', 'desktop frame', children=[owner])
    ui = ui_for(desktop)
    ui.require_child_overlay_session = Mock()
    ui.api.Text = SimpleNamespace(get_character_count=lambda interface: interface.get_character_count())
    monkeypatch.setattr(a.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(a, 'Path', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=1001)))
    return ui, desktop, owner, dialog, field, cancel, recipient, message


@pytest.mark.parametrize('fault,code', [
    ('provider', 'wrong-agent'), ('owner', 'owner'), ('session', 'session'),
    ('recipient', 'recipient-context-missing'), ('child', 'request-context-missing'),
    ('duration', 'request-context-missing'), ('apps', 'request-context-missing'),
    ('negated-apps', 'request-context-missing'),
    ('conflicting-apps', 'request-context-missing'),
    ('conflicting-child', 'request-context-missing'),
    ('extended-child-name', 'request-context-missing'),
    ('wrong-unit', 'request-context-missing'),
    ('numeric-substring', 'request-context-missing'),
    ('signed-time', 'request-context-missing'),
    ('fractional-time', 'request-context-missing'),
    ('conflicting-time', 'request-context-missing'),
    ('ambiguous', 'field-ambiguous'), ('hidden', 'field-state'), ('disabled', 'field-state'),
    ('unfocused', 'field-state'), ('nonempty', 'field-not-empty'), ('stale', 'owner'),
    ('replaced', 'replacement'), ('missing', 'replacement'), ('wrong-child-session', 'overlay-account')])
def test_wrong_or_stale_challenge_refuses_before_cancel(monkeypatch, fault, code):
    ui, desktop, owner, dialog, field, cancel, recipient, message = prompt(monkeypatch)
    challenge = ui.shell_prompt(100, 1001)
    pid, uid = 100, 1001
    if fault == 'provider': owner.name = 'mate-polkit'
    elif fault == 'owner': pid = 999
    elif fault == 'session': uid = 999
    elif fault == 'recipient': recipient.name = a.OTHER_PARENT
    elif fault == 'child': message.name = message.name.replace(a.CHILD, a.EXISTING_CHILD)
    elif fault == 'duration': message.name = message.name.replace('1 minute, 15 seconds', '30 minutes')
    elif fault == 'apps': message.name = f'Grant access to {a.CHILD}\nfor 1 minute, 15 seconds'
    elif fault == 'negated-apps':
        message.name = f'Grant {a.CHILD} 1 minute, 15 seconds; do not allow soft blocked apps.'
    elif fault == 'conflicting-apps': message.name += '\nSoft-blocked apps not allowed'
    elif fault == 'conflicting-child': message.name += '\n' + a.EXISTING_CHILD
    elif fault == 'extended-child-name': message.name = message.name.replace(a.CHILD, a.CHILD + 'ish')
    elif fault == 'wrong-unit': message.name = message.name.replace('15 seconds', '15 minutes')
    elif fault == 'numeric-substring': message.name = message.name.replace('15 seconds', '115 seconds')
    elif fault == 'signed-time': message.name = message.name.replace('15 seconds', '-15 seconds')
    elif fault == 'fractional-time': message.name = message.name.replace('15 seconds', '0.15 seconds')
    elif fault == 'conflicting-time': message.name += '\n30 seconds'
    elif fault == 'ambiguous': cancel.role = 'password text'
    elif fault in ('hidden', 'disabled', 'unfocused'):
        field.states.discard({'hidden': 'showing', 'disabled': 'sensitive', 'unfocused': 'focused'}[fault])
    elif fault == 'nonempty': field.length = 1
    elif fault == 'stale': field.states.add('defunct')
    elif fault == 'replaced': challenge = (owner, dialog, cancel, field)
    elif fault == 'missing': desktop.children.clear()
    elif fault == 'wrong-child-session': ui.require_child_overlay_session.side_effect = a.UiError('ui:overlay-account')
    with pytest.raises(a.UiError, match='ui:(shell-' + code + '|' + code + ')'):
        ui.shell_prompt(pid, uid, challenge=challenge)
    cancel.action.do_action.assert_not_called()
    if code in ('recipient-context-missing', 'request-context-missing'):
        assert field.get_text_iface.call_count == 1  # initial valid proof only


@pytest.mark.parametrize('fault', [None, 'formatting', 'english-message', 'english-binding', 'wrong-child', 'apps'])
def test_hebrew_context_is_bound_before_protected_field_access(monkeypatch, fault):
    ui, _, _, _, field, cancel, _, message = prompt(monkeypatch)
    # Literal oracle from the Hebrew product catalogue, independent of the guard.
    message.name = (f'להעניק גישה ל־{a.CHILD}\nלמשך 1 דקה, 15 שניות\n\n'
                    '✓ יישומים החסומים עם אפשרות להיתר זמני מותרים')
    if fault == 'english-message':
        message.name = (f'Grant access to {a.CHILD}\nfor 1 minute, 15 seconds\n\n'
                        '✓ Soft-blocked apps allowed')
    elif fault == 'wrong-child':
        message.name = message.name.replace(a.CHILD, a.EXISTING_CHILD)
    elif fault == 'apps': message.name = message.name.replace('מותרים', 'אינם מותרים')
    elif fault == 'formatting': message.name = '\u200f' + message.name.replace('\n', '  ')
    if fault not in (None, 'formatting'):
        with pytest.raises(a.UiError, match='ui:shell-request-context-missing'):
            ui.shell_prompt(100, 1001, language='en' if fault == 'english-binding' else 'he')
        field.get_text_iface.assert_not_called()
    else:
        challenge = ui.shell_prompt(100, 1001, language='he')
        assert challenge[2] is field
        assert ui.shell_prompt_refusals(100, 1001, challenge, language='he') == list(a.SHELL_PROMPT_REFUSALS)
    cancel.get_action_iface.assert_not_called()
    field.get_description.assert_not_called()


@pytest.mark.parametrize('binding,child,parent,message', [
    (('child', 'parent', 30, False), a.CHILD, a.PARENT,
     'Grant access to Riley (Child)\nfor 30 seconds\n\n✗ Soft-blocked not allowed'),
    (('child', 'parent', 30, False), a.CHILD, a.PARENT,
     'Grant Riley (Child) access? Requested time: 30 seconds. Soft blocked apps not permitted.'),
    (('other-child', 'other-parent', 75, True), a.EXISTING_CHILD, a.OTHER_PARENT,
     'Grant Jordan (Child) access?\nRequested time: 1 minute, 15 seconds.\nAllow soft blocked apps for this grant.'),
    (('other-child', 'other-parent', 75, True), a.EXISTING_CHILD, a.OTHER_PARENT,
     'Grant access to Jordan (Child)\nfor 1 minute, 15 seconds\n\n✓ Soft-blocked apps allowed'),
    (('other-child', 'other-parent', 75, True), a.EXISTING_CHILD, a.OTHER_PARENT,
     'Please grant Jordan (Child) access: 75 seconds.\nSoft-blocked apps permitted.'),
    (('child', 'parent', 30, False), a.CHILD, a.PARENT,
     '\u200eGrant access to Riley (Child):\t30\u00a0seconds!\nSoft—blocked apps NOT allowed.'),
])
def test_bound_shell_context_precedes_protected_field_access(monkeypatch, binding, child, parent, message):
    ui, _, _, _, field, _, recipient, text = prompt(monkeypatch)
    ui.overlay_request = binding
    recipient.name, text.name = parent, message
    challenge = ui.shell_prompt(100, 1001)
    assert challenge[2] is field
    assert ui.shell_prompt_refusals(100, 1001, challenge) == list(a.SHELL_PROMPT_REFUSALS)
    ui.require_child_overlay_session.assert_called_with(child)
    field.get_text_iface.reset_mock()
    text.name = (message.replace('not allowed', 'allowed').replace('not permitted', 'permitted')
                 .replace('NOT allowed', 'allowed') if not binding[3]
                 else message + '\nSoft blocked apps not allowed')
    with pytest.raises(a.UiError, match='request-context-missing'):
        ui.shell_prompt(100, 1001)
    field.get_text_iface.assert_not_called()
    text.name = message
    recipient.name = a.OTHER_PARENT if parent == a.PARENT else a.PARENT
    with pytest.raises(a.UiError, match='recipient-context-missing'):
        ui.shell_prompt(100, 1001)
    field.get_text_iface.assert_not_called()


def test_request_binding_cannot_change_between_shell_recipient_proofs():
    observer = UiObservations(Mock(commands=SimpleNamespace(progress=None)))
    observer.shell_approval_index = 1
    observer.shell_request_binding = ('child', 'parent', 30, False)
    observer.overlay_request = ('other-child', 'other-parent', 75, True)
    observer.shell_approval_checked = a.time.monotonic()
    observer._observe = Mock()
    with pytest.raises(EvidenceError, match='shell-request-replaced'):
        observer.observe('overlay-shell-qualified')
    observer._observe.assert_not_called()
    assert observer.challenge_failed


@pytest.mark.parametrize('fault', [None, 'prefix', 'binding', 'proof', 'repeat'])
def test_composed_shell_credential_uses_exact_owner_and_two_fresh_proofs(fault):
    program = r'''
use strict; use warnings; use JSON::PP;
our $fault = shift @ARGV; our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { 1 }
sub get_required_var { push @main::events, $_[0]; 'synthetic-fixture-only' }
sub type_password { push @main::events, 'password'; }
package main;
require onpc_journey; require onpc_password;
my $journey = onpc_journey->new(prefix => $fault eq 'prefix' ? 'unknown' : 'overlay-approval-return',
    review => 0, exchange => sub {
        my ($stage) = @_; push @events, $stage;
        return {observed => $fault eq 'proof' ? 'wrong' : $stage};
    });
$journey->{overlay_request} = ['other-child', 'other-parent', $fault eq 'binding' ? 999 : 75, 1];
my $ok = eval { onpc_password::enter_overlay_shell_password($journey); 1 };
my $before = scalar @events;
my $retry = eval { onpc_password::enter_overlay_shell_password($journey); 1 };
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0, before => $before, events => \@events});
'''
    value = json.loads(run_perl(program, fault or '').stdout)
    assert bool(value['ok']) == (fault in (None, 'repeat'))
    assert not value['retry'] and value['before'] == len(value['events'])
    if value['ok']:
        assert value['events'] == ['approval-qualified', 'approval-rechecked',
                                   '_SECRET_ONPC_OTHER_PARENT_PASSWORD', 'password']
    else:
        assert 'password' not in value['events']


@pytest.mark.parametrize('index,operation', [(1, 'overlay-shell-qualified'), (4, 'overlay-approval-immediate')])
def test_translated_challenge_cannot_switch_language_between_recipient_proofs(index, operation):
    observer = UiObservations(Mock(commands=SimpleNamespace(progress=None)))
    observer.shell_approval_index = index
    observer.shell_hebrew = True
    observer.shell_approval_checked = a.time.monotonic()
    observer._observe = Mock()
    with pytest.raises(EvidenceError, match='ui:shell-order'):
        observer.observe(operation)
    observer._observe.assert_not_called()
    assert observer.challenge_failed


@pytest.mark.parametrize('fault', ['missing', 'ambiguous', 'nested', 'foreign-user', 'stale'])
def test_fullscreen_prompt_entry_refuses_unbound_shell_owner_before_submission(monkeypatch, fault):
    ui, desktop, owner, dialog, *_ = prompt(monkeypatch)
    owner.children.clear()
    ui.kiosk_valid_choice = Mock()
    submit = Node('Request')
    ui.kiosk_valid_target = Mock(return_value=submit)
    if fault == 'missing': desktop.children.clear()
    elif fault == 'ambiguous': desktop.children.append(Node('gnome-shell', 'application'))
    elif fault == 'nested': owner.get_parent = lambda: dialog
    elif fault == 'foreign-user':
        monkeypatch.setattr(a, 'Path', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=1002)))
    elif fault == 'stale': owner.states.add('defunct')
    with pytest.raises(a.UiError, match='ui:shell-owner'):
        ui.run('overlay-shell-cancel-ready', '')
    submit.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'replacement', 'recipient', 'empty', 'unfocused', 'stale'])
def test_approval_filled_submit_guard_never_delivers_input(monkeypatch, fault):
    operation = 'overlay-shell-submit-ready'
    ui, _, _, _, field, cancel, recipient, _ = prompt(monkeypatch)
    ui.expected_mate_challenge = 'a' * 64
    ui.mate_challenge_identity = Mock(return_value=('b' if fault == 'replacement' else 'a') * 64)
    field.length = 0 if fault == 'empty' else 12
    if fault == 'recipient': recipient.name = a.OTHER_PARENT
    if fault == 'unfocused': field.states.discard('focused')
    if fault == 'stale': field.states.add('defunct')
    if fault:
        with pytest.raises(a.UiError): ui.run(operation, '')
    else:
        assert ui.run(operation, '')['approval'] == {'challenge_id': 'a' * 64}
    with pytest.raises(a.UiError, match='uncertain'): ui.run(operation, '')
    cancel.get_action_iface.assert_not_called()
    field.get_description.assert_not_called()
    field.get_child_count.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'boot', 'challenge', 'duplicate', 'missing',
                                  'stale', 'recording', 'input', 'extra'])
def test_live_observer_readiness_is_durable_bound_and_single_use(monkeypatch, fault):
    operation = 'overlay-approval-success'
    transport = Mock(commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    observer.shell_approval_index = 4
    observer.shell_approval_identity = 'a' * 64
    observer.shell_approval_checked = a.time.monotonic()
    observer.boot_guard = 'c' * 64
    events = []

    def retain(*args):
        events.append('durable')
        if fault == 'recording': raise OSError('recording')

    def submit(token, source):
        assert token == 'a' * 32 and source == 'a' * 64
        events.append('enter')
        if fault == 'input': raise RuntimeError('uncertain')

    observer.trace_sink = retain
    def call(_argv, *, on_output, **kwargs):
        ready = {'event': 'overlay-approval-ready', 'challenge_id': 'a' * 64,
                 'boot_sha256': 'c' * 64}
        if fault == 'boot': ready['boot_sha256'] = 'd' * 64
        if fault == 'challenge': ready['challenge_id'] = 'd' * 64
        if fault == 'extra': ready['unexpected'] = True
        if fault == 'stale': observer.shell_approval_checked -= 31
        if fault != 'missing': on_output((json.dumps(ready) + '\n').encode())
        if fault == 'duplicate': on_output((json.dumps(ready) + '\n').encode())
        result = {'operation': operation, 'outcome': 'passed',
                  'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'c' * 64,
                  'approval': {'approved': True, 'form_success': True}}
        on_output((json.dumps(result) + '\n').encode())
    transport.call.side_effect = call
    if fault:
        with pytest.raises((EvidenceError, OSError, RuntimeError)):
            observer.observe_shell_success(submit, operation=operation)
        assert observer.challenge_failed
    else:
        assert observer.observe_shell_success(submit, operation=operation)['approval']['form_success']
        assert events == ['durable', 'enter']
    assert events.count('enter') == (1 if fault in (None, 'duplicate', 'input') else 0)
    assert observer.shell_success_input is None
    before = list(events)
    with pytest.raises(EvidenceError): observer.observe_shell_success(submit, operation=operation)
    assert events == before


@pytest.mark.parametrize('fault', [None, 'missing', 'binding', 'source', 'values', 'duplicate', 'input'])
def test_worker_enter_waits_for_observer_and_never_replays(fault):
    program = r'''
use strict; use warnings; use JSON::PP;
our $fault = shift @ARGV; our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, 'enter'; die 'uncertain' if $main::fault eq 'input'; }
package main;
require onpc_request_flow;
no warnings 'redefine';
*onpc_password::enter_overlay_shell_password = sub { push @events, 'password'; };
my $journey = onpc_journey->new(prefix => 'overlay-approved-exit', review => 0,
    exchange => sub {
        my ($stage, $shot, $input) = @_; push @events, $stage;
        if (defined($input) && $fault ne 'missing') {
            push @events, 'observer-ready';
            my $proof = {stage => $stage, token => 'a' x 32, source => 'a' x 64,
                         child => 'child', binding => 'overlay-approve', values => ['ret']};
            $proof->{binding} = 'custom-rapid' if $fault eq 'binding';
            $proof->{source} = 'b' x 64 if $fault eq 'source';
            $proof->{values} = ['ret', 'ret'] if $fault eq 'values';
            $input->($proof);
            $input->($proof) if $fault eq 'duplicate';
        }
        return {observed => $stage};
    });
my $ok = eval { onpc_request_flow::shell_approve($journey); 1 };
my $before = scalar @events;
my $retry = eval { onpc_request_flow::shell_approve($journey); 1 };
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0,
                   before => $before, events => \@events});
'''
    value = json.loads(run_perl(program, fault or '').stdout)
    assert bool(value['ok']) == (fault is None)
    assert not value['retry'] and len(value['events']) == value['before']
    assert value['events'].count('enter') == (1 if fault in (None, 'duplicate', 'input') else 0)
    if 'enter' in value['events']:
        assert value['events'].index('observer-ready') < value['events'].index('enter')


@pytest.mark.parametrize('fault', [None, 'missing', 'token', 'stage', 'symlink'])
def test_shell_rendezvous_uses_owned_evidence_and_requires_exact_ack(tmp_path, fault):
    journey = ApprovalReturnJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.publish_trace_input('approval-success', 'a' * 32, 'a' * 64)
    assert json.loads((tmp_path / 'approval-success.input.json').read_bytes()) == {
        'stage': 'approval-success', 'token': 'a' * 32, 'source': 'a' * 64,
        'child': 'child', 'binding': 'overlay-approve', 'values': ['ret']}
    with pytest.raises(EvidenceError, match='replay'):
        journey.publish_trace_input('approval-success', 'a' * 32, 'a' * 64)
    with pytest.raises(EvidenceError, match='plan'):
        journey.publish_trace_input('approval-submit-ready', 'a' * 32, 'a' * 64)
    done = tmp_path / 'approval-success.input-done.json'
    if fault != 'missing':
        value = {'stage': 'wrong' if fault == 'stage' else 'approval-success',
                 'token': ('b' if fault == 'token' else 'a') * 32}
        if fault == 'symlink':
            target = tmp_path / 'foreign.json'
            target.write_text(json.dumps(value))
            done.symlink_to(target)
        else:
            done.write_text(json.dumps(value))
    if fault:
        with pytest.raises(EvidenceError, match='incomplete'):
            journey.verify_trace_input('approval-success', 'a' * 32)
    else:
        journey.verify_trace_input('approval-success', 'a' * 32)
