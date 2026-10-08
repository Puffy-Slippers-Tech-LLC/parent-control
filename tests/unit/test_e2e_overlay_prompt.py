"""Shell AUTH01 context, protected input, decoder and independent attempt guards.

Parallelism: in-memory trees/doubles and private tmp_path, no live VM/display.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import accessible_ui as a
import check_e2e_overlay_prompt as selector
from overlay_prompt import PLAN, OverlayPromptJourney
from overlay_approved_exit import PLAN as APPROVED_PLAN
from overlay_approved_exit import OverlayApprovedExitJourney
from overlay_rejection import PLAN as REJECTION_PLAN, OverlayRejectionJourney
from parent_setup_qualification import OverlayRejectionQualification
from parent_setup_qualification import OverlayApprovedExitQualification
from parent_setup_qualification import OverlayPromptQualification, KioskEntryQualification
from private_artifacts import EvidenceError
from request_flow import overlay_authentication
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from ui_observations import UiObservations, OPERATION_LABELS


@pytest.mark.parametrize('result,operations', [
    ('cancel', ['overlay-shell-cancel-ready', 'overlay-shell-dismissed']),
    ('approval', ['overlay-shell-open', 'overlay-shell-qualified',
                  'overlay-shell-rechecked', 'overlay-shell-submit-ready', 'overlay-approval-success']),
    ('rejection', [*a.SHELL_REJECTION_ORDER, 'overlay-shell-dismissed']),
])
def test_shared_authentication_fragment_supports_independent_checkpoints(result, operations):
    stages = overlay_authentication(result=result, prefix='independent-auth')
    assert list(stages.values()) == ['ui:' + operation for operation in operations]
    assert all(stage.startswith('independent-auth-') for stage in stages)
    plan = {'cancel': PLAN, 'approval': APPROVED_PLAN, 'rejection': REJECTION_PLAN}[result]
    assert [operation for operation in plan.screen_tags.values()
            if operation in stages.values()] == list(stages.values())
    stages.clear()
    assert len(overlay_authentication(result=result, prefix='another-auth')) == len(operations)


@pytest.mark.parametrize('result,prefix', [('unknown', 'auth'), ('cancel', ''),
                                        ('approval', None), ('cancel', 'auth/path')])
def test_shared_authentication_fragment_refuses_undeclared_bindings(result, prefix):
    with pytest.raises(EvidenceError):
        overlay_authentication(result=result, prefix=prefix)


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
    message = Node(f'Grant {a.CHILD} access?\nRequested time: 1 minute, 15 seconds.\n'
                   'Allow soft blocked apps for this grant.', 'label')
    dialog = Node('Authentication Required', 'dialog', children=[recipient, message, field, cancel])
    owner = Node('gnome-shell', 'application', children=[dialog])
    desktop = Node('desktop', 'desktop frame', children=[owner])
    ui = ui_for(desktop)
    ui.require_child_overlay_session = Mock()
    ui.api.Text = SimpleNamespace(get_character_count=lambda interface: interface.get_character_count())
    monkeypatch.setattr(a.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(a, 'Path', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=1001)))
    return ui, desktop, owner, dialog, field, cancel, recipient, message


def test_independent_real_tree_proof_and_refusal_matrix_never_reads_secret(monkeypatch):
    ui, _, owner, dialog, field, cancel, *_ = prompt(monkeypatch)
    challenge = ui.shell_prompt(100, 1001)
    assert challenge == (owner, dialog, field, cancel)
    assert ui.shell_prompt_refusals(100, 1001, challenge) == list(a.SHELL_PROMPT_REFUSALS)
    assert ui.shell_prompt(100, 1001, challenge=challenge) == challenge
    field.get_description.assert_not_called()
    field.get_child_count.assert_not_called()
    cancel.get_action_iface.assert_not_called()


@pytest.mark.parametrize('fault,code', [
    ('provider', 'wrong-agent'), ('owner', 'owner'), ('session', 'session'),
    ('recipient', 'recipient-context-missing'), ('child', 'request-context-missing'),
    ('duration', 'request-context-missing'), ('apps', 'request-context-missing'),
    ('obsolete-message', 'request-context-missing'),
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
    elif fault == 'apps': message.name = f'Grant {a.CHILD} access?\nRequested time: 1 minute, 15 seconds.'
    elif fault == 'obsolete-message':
        message.name = f'Grant {a.CHILD} 1 minute, 15 seconds and allow soft blocked apps?'
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
    if fault in ('recipient', 'child', 'duration', 'apps', 'obsolete-message'):
        assert field.get_text_iface.call_count == 1  # initial valid proof only


def proof_value():
    return {'operation': 'overlay-shell-cancel-ready', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
        'shell_prompt': {'provider': {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]},
            'child': 'fixture-child', 'approver': 'fixture-parent', 'duration_seconds': 75,
            'allow_soft': True, 'cancel_ready': True, 'same_challenge_rechecked': True,
            'rejected_proofs': list(a.SHELL_PROMPT_REFUSALS), 'challenge_id': 'a' * 64}}


@pytest.mark.parametrize('fault', ['transient-query', 'persistent-query', 'incomplete'])
def test_wrong_surface_refusal_requires_complete_reacquisition(monkeypatch, fault):
    from gi.repository import Gio, GLib
    from itertools import count
    owner = Node(identity=a.CHILD_APPLICATION, role='application')
    ui = ui_for(Node(role='desktop frame', children=[owner]))
    ui.require_child_overlay_session = Mock()
    ui.query_errors = (GLib.Error,)
    ui.timeout = 1
    clock = count(0, .1)
    monkeypatch.setattr(a, 'time', SimpleNamespace(
        monotonic=lambda: next(clock), sleep=lambda _: None))
    read = ui._read_nodes
    reads = []

    def unavailable(*args, **kwargs):
        reads.append(True)
        if fault == 'persistent-query' or len(reads) == 1:
            if fault == 'incomplete':
                raise a.UiError('ui:incomplete-tree')
            raise Gio.DBusError.new_for_dbus_error(
                'org.freedesktop.DBus.Error.ServiceUnknown', 'PRIVATE_PROVIDER')
        yield from read(*args, **kwargs)

    monkeypatch.setattr(ui, '_read_nodes', unavailable)
    if fault == 'persistent-query':
        ui.kiosk_valid_target = Mock(side_effect=AssertionError('no proof from incomplete read'))
        with pytest.raises(a.UiError, match='ui:timeout:overlay-refusal-observation'):
            ui.run('overlay-valid-refusals', '')
        ui.kiosk_valid_target.assert_not_called()
    else:
        assert ui.run('overlay-valid-refusals', '')['outcome'] == 'passed'
        assert len(reads) == 2  # Both refusal checks reuse the complete reread.
    owner.action.do_action.assert_not_called()
    owner.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'replacement', 'uncertain-submit', 'wrong-form'])
@pytest.mark.parametrize('operation', ['overlay-shell-cancel-ready', 'overlay-shell-open', a.SHELL_REJECTION_ORDER[0]])
def test_real_open_sequence_rechecks_before_releasing_keyboard_input(monkeypatch, capsys, fault, operation):
    ui, desktop, owner, dialog, field, cancel, *_ = prompt(monkeypatch)
    # A fullscreen overlay need not expose Shell's Activities control. The
    # application still owns the forthcoming prompt on the child's public bus.
    owner.children.clear()
    def form_reader(_operation):
        if fault == 'wrong-form': raise a.UiError('ui:wrong-form')
        diagnostic = a.KioskDiagnostic()
        diagnostic.emit('public-tree')
        diagnostic.emit('form-tree')
    ui.kiosk_valid_choice = Mock(side_effect=form_reader)
    assert ui.shell_desktop_observation(no_prompt=True) is None
    submit = Node('Request')
    def submit_once(_):
        owner.children.append(dialog)
        if fault == 'uncertain-submit': raise RuntimeError('uncertain')
        return True
    submit.action.do_action.side_effect = submit_once
    ui.kiosk_valid_target = Mock(return_value=submit)
    ui._shell_provider_metadata = Mock(return_value=proof_value()['shell_prompt']['provider'])
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    original = ui.shell_prompt_refusals
    def refusals(*args):
        result = original(*args)
        if fault == 'replacement': dialog.children.remove(field)
        return result
    ui.shell_prompt_refusals = refusals
    if fault:
        with pytest.raises((a.UiError, RuntimeError)): ui.run(operation, '')
        with pytest.raises(a.UiError): ui.run(operation, '')
    else:
        result = ui.run(operation, '')
        expected = (proof_value() if operation == 'overlay-shell-cancel-ready' else {
            'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', 'approval': {
                'challenge_id': 'a' * 64, 'provider': proof_value()['shell_prompt']['provider'],
                'rejected_proofs': list(a.SHELL_PROMPT_REFUSALS)}})
        assert result == expected
        raw = capsys.readouterr().out.encode() + (json.dumps(result) + '\n').encode()
        transport = Mock(commands=SimpleNamespace(progress=None))
        def call(*_args, on_output, **_kwargs):
            for offset in range(0, len(raw), 97): on_output(raw[offset:offset + 97])
            return raw
        transport.call.side_effect = call
        observer = UiObservations(transport)
        assert observer.observe(operation) == result
        with pytest.raises(Exception, match='ui:(challenge-replay|shell-order)'): observer.observe(operation)
        assert observer.challenge_failed
    assert submit.action.do_action.call_count == (0 if fault == 'wrong-form' else 1)
    cancel.action.do_action.assert_not_called()


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


@pytest.mark.parametrize('fault', ['provider', 'extra', 'recipient', 'refusals', 'rechecked'])
def test_decoder_refuses_malformed_proof_and_latches_failure(fault):
    value = proof_value()
    if fault == 'provider': value['shell_prompt']['provider']['locale'] = ''
    elif fault == 'extra': value['shell_prompt']['raw_label'] = 'private'
    elif fault == 'recipient': value['shell_prompt']['approver'] = 'other-fixture-parent'
    elif fault == 'refusals': value['shell_prompt']['rejected_proofs'].pop()
    elif fault == 'rechecked': value['shell_prompt']['same_challenge_rechecked'] = False
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(value).encode(), []))
    with pytest.raises(Exception): observer.observe('overlay-shell-cancel-ready')
    assert observer.challenge_failed
    with pytest.raises(Exception): observer.observe('overlay-shell-cancel-ready')
    assert observer.call.call_count == 1


def test_registration_reuses_owned_snapshot_envelope():
    context = SimpleNamespace()
    journey = OverlayPromptQualification.journey(context, Mock())
    assert journey.plan is PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    assert OverlayPromptQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    operations = {tag[3:] for tag in PLAN.screen_tags.values() if tag.startswith('ui:')}
    assert operations <= a.OPERATIONS & OPERATION_LABELS.keys()
    assert a.SHELL_PROMPT_OPERATIONS <= a.CHILD_DESKTOP_OPERATIONS
    assert not a.SHELL_PROMPT_OPERATIONS & a.KIOSK_SESSION_OPERATIONS


def test_rejection_registration_retains_owned_envelope():
    context = SimpleNamespace()
    journey = OverlayRejectionQualification.journey(context, Mock())
    assert journey.plan is REJECTION_PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    assert OverlayRejectionQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert {tag[3:] for tag in REJECTION_PLAN.screen_tags.values() if tag.startswith('ui:')} <= a.OPERATIONS & OPERATION_LABELS.keys()
    assert set(a.SHELL_REJECTION_ORDER) <= a.CHILD_DESKTOP_OPERATIONS
    assert not set(a.SHELL_REJECTION_ORDER) & a.KIOSK_SESSION_OPERATIONS


@pytest.mark.parametrize('fault', [None, 'missing', 'duplicate', 'hidden', 'success',
                                  'replaced', 'recipient', 'provider', 'nonempty',
                                  'disabled', 'unfocused', 'stale', 'delayed'])
def test_rejection_requires_explicit_owned_denial_and_fresh_retry_field(monkeypatch, fault):
    ui, desktop, owner, dialog, field, cancel, recipient, _ = prompt(monkeypatch)
    ui.timeout = 0.05
    ui.expected_mate_challenge = 'a' * 64
    ui.mate_challenge_identity = Mock(return_value=('b' if fault == 'replaced' else 'a') * 64)
    label = Node('Sorry, that didn’t work. Please try again.', 'label')
    if fault != 'missing': dialog.children.append(label)
    if fault == 'duplicate': dialog.children.append(Node(label.name, 'label'))
    if fault == 'hidden': label.states.discard('showing')
    if fault == 'success': owner.children.clear()
    if fault == 'recipient': recipient.name = a.OTHER_PARENT
    if fault == 'provider': owner.name = 'mate-polkit'
    if fault == 'nonempty': field.length = 12
    if fault == 'disabled': field.states.discard('sensitive')
    if fault == 'unfocused': field.states.discard('focused')
    if fault == 'stale': field.states.add('defunct')
    if fault == 'delayed':
        field.states.discard('sensitive')
        original = ui.wait
        def wait(predicate, *args, **kwargs):
            assert not predicate()  # Label alone cannot release Escape.
            field.states.add('sensitive')
            return original(predicate, *args, **kwargs)
        ui.wait = wait
    if fault not in (None, 'delayed'):
        with pytest.raises(a.UiError): ui.run(a.SHELL_REJECTION_ORDER[-1], '')
    else:
        assert ui.run(a.SHELL_REJECTION_ORDER[-1], '')['approval'] == {
            'challenge_id': 'a' * 64, 'rejected': True, 'cancel_ready': True,
            'same_challenge_rechecked': True}
    with pytest.raises(a.UiError, match='uncertain'):
        ui.run(a.SHELL_REJECTION_ORDER[-1], '')
    cancel.get_action_iface.assert_not_called()
    field.get_description.assert_not_called()
    field.get_child_count.assert_not_called()


@pytest.mark.parametrize('fault', ['denied', 'ready', 'rechecked', 'identity', 'extra', 'numeric'])
def test_rejection_decoder_never_releases_cancel_for_incomplete_result(fault):
    observer = UiObservations(Mock())
    observer.shell_approval_index = 4
    observer.shell_rejection = True
    observer.shell_approval_identity = 'a' * 64
    observer.shell_approval_checked = a.time.monotonic()
    value = {'challenge_id': 'a' * 64, 'rejected': True, 'cancel_ready': True,
             'same_challenge_rechecked': True}
    if fault in ('denied', 'ready', 'rechecked'):
        value[{'denied': 'rejected', 'ready': 'cancel_ready', 'rechecked': 'same_challenge_rechecked'}[fault]] = False
    elif fault == 'identity': value['challenge_id'] = 'b' * 64
    elif fault == 'extra': value['private'] = 'canary'
    elif fault == 'numeric': value['rejected'] = 1
    operation = a.SHELL_REJECTION_ORDER[-1]
    observer.call = Mock(return_value=(json.dumps({'operation': operation, 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'approval': value,
        'boot_sha256': 'c' * 64}).encode(), []))
    with pytest.raises(EvidenceError): observer.observe(operation)
    assert observer.challenge_failed
    with pytest.raises(EvidenceError): observer.observe(operation)
    assert observer.call.call_count == 1


@pytest.mark.parametrize('fault', ['', 'open', 'qualified', 'rechecked', 'submit-ready', 'cancel-ready',
                                  'dismissed', 'ret', 'esc'])
def test_shared_rejection_uses_renamed_endpoints_and_stops_before_later_input(fault):
    program = r'''
use strict; use warnings; use JSON::PP;
our @events; our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { 1 }
sub get_required_var { 'fixture-only-canary' }
sub type_password { die 'wrong-input' unless $_[0] eq 'onpc-wrong-fixture-password'; push @main::events, ['wrong-password']; }
sub send_key { push @main::events, ['key', $_[0]]; die 'uncertain' if $main::fault eq $_[0]; }
package main;
require onpc_request_flow;
my $journey = onpc_journey->new(prefix => 'overlay-rejection', review => 0, exchange => sub {
    my ($stage) = @_; push @events, ['stage', $stage];
    die 'refused' if $stage eq 'independent-' . $fault;
    return {observed => $stage};
});
my $ok = eval { onpc_request_flow::shell_reject($journey, 'independent'); 1 };
my $before = scalar @events;
my $again = eval { onpc_request_flow::shell_reject($journey, 'independent'); 1 };
print encode_json({ok => $ok ? 1 : 0, replay => $again ? 1 : 0, before => $before, events => \@events});
'''
    raw = run_perl(program, fault).stdout
    assert 'fixture-only-canary' not in raw
    result = json.loads(raw)
    expected = ([['stage', 'independent-' + suffix] for suffix in ('open', 'qualified', 'rechecked')]
                + [['wrong-password'], ['stage', 'independent-submit-ready'], ['key', 'ret'],
                   ['stage', 'independent-cancel-ready'], ['key', 'esc'], ['stage', 'independent-dismissed']])
    boundary = (['key', fault] if fault in ('ret', 'esc') else ['stage', 'independent-' + fault])
    assert result['events'] == (expected[:expected.index(boundary) + 1] if fault else expected)
    assert bool(result['ok']) == (not fault)
    assert not result['replay'] and len(result['events']) == result['before']


def test_approval_registration_retains_owned_envelope(monkeypatch):
    import check_e2e_overlay_approved_exit as approved_selector
    smoke = Mock(return_value=0)
    monkeypatch.setattr(approved_selector, 'smoke', smoke)
    named = Mock(return_value='owned-input')
    monkeypatch.setattr(approved_selector, 'named_input', named)
    assert approved_selector.main() == 0
    named.assert_called_once_with(fixture_source=True)
    smoke.assert_called_once_with(assets='owned-input', provision_credentials=True,
                                 challenges=True, challenge_profile='overlay-approved-exit')
    context = SimpleNamespace()
    journey = OverlayApprovedExitQualification.journey(context, Mock())
    assert journey.plan is APPROVED_PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    assert OverlayApprovedExitQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert {tag[3:] for tag in APPROVED_PLAN.screen_tags.values() if tag.startswith('ui:')} <= a.OPERATIONS & OPERATION_LABELS.keys()
    assert a.SHELL_APPROVAL_OPERATIONS <= a.CHILD_DESKTOP_OPERATIONS
    assert not a.SHELL_APPROVAL_OPERATIONS & a.KIOSK_SESSION_OPERATIONS


def test_kiosk_regression_binds_current_package_and_retains_owned_envelope(monkeypatch):
    import check_e2e_kiosk_approval as kiosk_selector
    smoke = Mock(return_value=0)
    named = Mock(return_value='current-input')
    monkeypatch.setattr(kiosk_selector, 'smoke', smoke)
    monkeypatch.setattr(kiosk_selector, 'named_input', named)
    assert kiosk_selector.main() == 0
    named.assert_called_once_with(package_source=True)
    smoke.assert_called_once_with(assets='current-input', provision_credentials=True,
                                  kiosk_approval=True)


@pytest.mark.parametrize('fault', [None, 'replacement', 'recipient', 'empty', 'unfocused', 'stale'])
@pytest.mark.parametrize('operation', ['overlay-shell-submit-ready', a.SHELL_REJECTION_ORDER[-2]])
def test_approval_filled_submit_guard_never_delivers_input(monkeypatch, fault, operation):
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


@pytest.mark.parametrize('fault', [None, 'wrong-owner', 'empty', 'unfocused', 'replaced',
                                  'duplicate', 'denied', 'hidden', 'missing', 'closing-query'])
def test_success_observer_is_ready_before_submit_and_reads_only_owned_window(monkeypatch, fault):
    ui, desktop, owner, dialog, field, *_ = prompt(monkeypatch)
    field.length = 12
    window = Node(identity='kiosk-request-window')
    app = Node('Child Request', 'application', identity=a.CHILD_APPLICATION, children=[window])
    desktop.children.append(app)
    app.get_parent = lambda: desktop
    window.get_parent = lambda: app
    ui.expected_mate_challenge = 'a' * 64
    ui.trace_boot = 'c' * 64
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    if fault == 'wrong-owner': app.identity = a.KIOSK_APPLICATION
    if fault == 'empty': field.length = 0
    if fault == 'unfocused': field.states.discard('focused')
    if fault == 'replaced': ui.expected_mate_challenge = 'b' * 64
    released = []
    original = ui.read_snapshot

    def snapshot(root=None, **kwargs):
        if released:
            assert root is window, 'late full-desktop read can miss the three-second result'
        return original(root, **kwargs)

    def publish(line, **kwargs):
        event = json.loads(line)
        assert event == {'event': 'overlay-approval-ready', 'challenge_id': 'a' * 64,
                         'boot_sha256': 'c' * 64}
        assert not released
        released.append(True)
        owner.children.remove(dialog)
        title = Node('Time granted', 'label', identity='kiosk-result-title')
        window.children.append(Node(identity='kiosk-result-page', children=[title]))
        if fault == 'duplicate': window.children.append(Node(identity='kiosk-result-title'))
        if fault == 'denied': title.name = 'Request denied'
        if fault == 'hidden': title.states.discard('showing')
        if fault == 'missing': window.children.clear()

    ui.read_snapshot = snapshot
    monkeypatch.setattr('builtins.print', publish)
    prompt_kind = ui.system_prompt_kind
    closing_reads = []
    def read_prompt(**kwargs):
        if not released:
            return prompt_kind(**kwargs)
        closing_reads.append(True)
        if fault == 'closing-query' and len(closing_reads) == 1:
            raise RuntimeError('owned overlay closed during read')
        return None
    ui.query_errors = (RuntimeError,)
    if fault == 'closing-query': ui.timeout = 1
    ui.system_prompt_kind = read_prompt
    if fault and fault != 'closing-query':
        with pytest.raises(a.UiError): ui.run('overlay-approval-success', '')
    else:
        assert ui.run('overlay-approval-success', '')['approval'] == {
            'approved': True, 'form_success': True}
    assert released == ([] if fault in ('wrong-owner', 'empty', 'unfocused', 'replaced') else [True])
    if fault == 'closing-query': assert len(closing_reads) == 2
    with pytest.raises(a.UiError, match='uncertain'): ui.run('overlay-approval-success', '')


@pytest.mark.parametrize('fault', [None, 'boot', 'challenge', 'duplicate', 'missing',
                                  'stale', 'recording', 'input', 'extra'])
def test_live_observer_readiness_is_durable_bound_and_single_use(monkeypatch, fault):
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
        result = {'operation': 'overlay-approval-success', 'outcome': 'passed',
                  'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'c' * 64,
                  'approval': {'approved': True, 'form_success': True}}
        on_output((json.dumps(result) + '\n').encode())
    transport.call.side_effect = call
    if fault:
        with pytest.raises((EvidenceError, OSError, RuntimeError)):
            observer.observe_shell_success(submit)
        assert observer.challenge_failed
    else:
        assert observer.observe_shell_success(submit)['approval']['form_success']
        assert events == ['durable', 'enter']
    assert events.count('enter') == (1 if fault in (None, 'duplicate', 'input') else 0)
    assert observer.shell_success_input is None
    before = list(events)
    with pytest.raises(EvidenceError): observer.observe_shell_success(submit)
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
    journey = OverlayApprovedExitJourney(SimpleNamespace(directory=tmp_path), Mock())
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


@pytest.mark.parametrize('fault', [None, 'changed', 'replay', 'intervening', 'order', 'stale', 'extra', 'provider', 'refusals'])
@pytest.mark.parametrize('rejection', [False, True])
def test_approval_decoder_enforces_same_challenge_order_and_terminal_failure(fault, rejection):
    observer = UiObservations(Mock())
    order = a.SHELL_REJECTION_ORDER if rejection else a.SHELL_APPROVAL_ORDER
    def call(_argv, operation, **_kwargs):
        value = {'challenge_id': ('b' if fault == 'changed' and operation == order[2] else 'a') * 64}
        if operation == order[0]:
            value.update(provider=proof_value()['shell_prompt']['provider'],
                         rejected_proofs=list(a.SHELL_PROMPT_REFUSALS))
            if fault == 'provider': value['provider']['locale'] = ''
            if fault == 'extra': value['raw'] = 'private label'
            if fault == 'refusals': value['rejected_proofs'].pop()
        if operation == 'overlay-approval-success': value = {'approved': True, 'form_success': True}
        if operation == a.SHELL_REJECTION_ORDER[-1]:
            value.update(rejected=True, cancel_ready=True, same_challenge_rechecked=True)
        return json.dumps({'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
                           'approval': value, **({'boot_sha256': 'c' * 64}
                               if operation in order[1:] else {})}).encode(), []
    observer.call = Mock(side_effect=call)
    if fault in ('extra', 'provider', 'refusals'):
        with pytest.raises(Exception): observer.observe(order[0])
    else:
        observer.observe(order[0])
        if fault:
            if fault == 'changed': observer.observe(order[1])
            if fault == 'stale': observer.shell_approval_checked = float('-inf')
            operation = {'changed': order[2], 'replay': order[0],
                         'intervening': 'desktop', 'order': order[3],
                         'stale': order[1]}[fault]
            with pytest.raises(Exception): observer.observe(operation)
        else:
            for operation in order[1:]: observer.observe(operation)
    if fault:
        assert observer.challenge_failed
        calls = observer.call.call_count
        with pytest.raises(Exception): observer.observe(order[1])
        assert observer.call.call_count == calls


@pytest.mark.parametrize('fault', [None, 'wrong-owner', 'denied', 'prompt', 'missing'])
def test_approval_success_requires_child_owned_public_result(monkeypatch, fault):
    title = Node('Request denied' if fault == 'denied' else 'Time granted', 'label',
                 identity='kiosk-result-title')
    page = Node(identity='kiosk-result-page', children=[title])
    window = Node(identity='kiosk-request-window', children=[page])
    # Build through the shared fixture's existing product owner, then bind the
    # actual child application without triggering its automatic kiosk wrapper.
    app = Node('Child Request', 'application', identity=a.KIOSK_APPLICATION, children=[window])
    ui = ui_for(Node('desktop', 'desktop frame', children=[app]))
    if fault != 'wrong-owner': app.identity = a.CHILD_APPLICATION
    ui.require_child_overlay_session = Mock()
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='shell-polkit')
    if fault == 'missing': window.children.clear()
    if fault:
        with pytest.raises(a.UiError): ui.kiosk_approval_success(overlay=True)
    else:
        assert ui.kiosk_approval_success(overlay=True) == {'approved': True, 'form_success': True}


@pytest.mark.parametrize('delay', ['opening', 'recipient', 'between-proofs'])
def test_shell_opening_work_does_not_age_future_recipient_authority(monkeypatch, delay):
    import time
    clock = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: clock[0])
    observer = UiObservations(Mock())
    def observe(operation):
        if operation == ('overlay-shell-open' if delay == 'opening' else 'overlay-shell-qualified'):
            clock[0] += 31
        return {'operation': operation}
    observer._observe = Mock(side_effect=observe)
    observer.observe('overlay-shell-open')
    observer.observe('overlay-shell-qualified')
    if delay == 'between-proofs':
        clock[0] += 30
    if delay == 'opening':
        for operation in a.SHELL_APPROVAL_ORDER[2:]:
            observer.observe(operation)
        assert not observer.challenge_failed
        assert observer._observe.call_count == len(a.SHELL_APPROVAL_ORDER)
    else:
        with pytest.raises(EvidenceError, match='ui:shell-stale-proof'):
            observer.observe('overlay-shell-rechecked')
        assert observer.challenge_failed
        with pytest.raises(EvidenceError, match='ui:challenge-previous-failure'):
            observer.observe('overlay-shell-rechecked')
        assert observer._observe.call_count == 2


@pytest.mark.parametrize('failure', [None, 0, 1])
@pytest.mark.parametrize('rejection', [False, True])
def test_two_owned_attempts_stop_after_first_failure(monkeypatch, failure, rejection):
    if rejection:
        import check_e2e_overlay_rejection as selected
    else:
        selected = selector
    smoke = Mock(side_effect=[1 if failure == 0 else 0, 1 if failure == 1 else 0])
    monkeypatch.setattr(selected, 'smoke', smoke)
    named = Mock(return_value='owned-input')
    monkeypatch.setattr(selected, 'named_input', named)
    assert selected.main() == (0 if failure is None else 1)
    assert smoke.call_count == (1 if failure == 0 else 2)
    assert named.call_args_list == [call(package_source=True)] * smoke.call_count
    for index, invocation in enumerate(smoke.call_args_list):
        assert invocation.kwargs == dict(assets='owned-input', provision_credentials=True,
                                         challenges=True, challenge_profile=(
                                             'overlay-rejection' if rejection and index == 0 else 'overlay-prompt'))


@pytest.mark.parametrize('fault', ['', 'proof', 'input', 'result'])
def test_shared_cancel_supports_renamed_endpoints_and_never_replays_uncertain_input(fault):
    program = r'''
use strict; use warnings; use JSON::PP;
our @events; our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, ['key', $_[0]]; die 'uncertain' if $main::fault eq 'input'; }
package main;
require onpc_request_flow;
my $journey = onpc_journey->new(prefix => 'independent-consumer', review => 0, exchange => sub {
    my ($stage) = @_; push @events, ['stage', $stage];
    die 'refused' if $fault eq 'proof' && $stage eq 'another-proof'
        || $fault eq 'result' && $stage eq 'another-result';
    return {observed => $stage};
});
my $ok = eval { onpc_request_flow::shell_cancel($journey, 'another-proof', 'another-result'); 1 };
my $again = $ok ? 0 : eval { onpc_request_flow::shell_cancel($journey, 'another-proof', 'another-result'); 1 };
print encode_json({ok => $ok ? 1 : 0, replay => $again ? 1 : 0, events => \@events});
'''
    result = json.loads(run_perl(program, fault).stdout)
    assert bool(result['ok']) == (not fault)
    assert not result['replay']
    assert result['events'] == ([['stage', 'another-proof']] if fault == 'proof' else
        [['stage', 'another-proof'], ['key', 'esc']] if fault == 'input' else
        [['stage', 'another-proof'], ['key', 'esc'], ['stage', 'another-result']])


@pytest.mark.parametrize('fault', [None, 'changed', 'missing', 'replay'])
def test_real_recorder_refuses_changed_choices_before_durable_reply(tmp_path, fault):
    from dataclasses import replace
    plan = replace(PLAN, screen_tags={'before': 'ui:overlay-valid-fraction-soft-read',
                                    'after': 'ui:overlay-valid-fraction-soft-read'},
                   phases={'ready': 'setup', 'setup-detached': 'setup', 'before': 'step-1', 'after': 'step-1'},
                   assertions_after={}, balance_checks={}, invocations=(), challenges={}, advance_after={},
                   request_checks={'after': ('before', 'shell:form-changed', 'preserved')})
    journey = OverlayPromptJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    value = {'surface': 'child-overlay', 'child': 'fixture-child', 'approver': 'fixture-parent',
             'duration_seconds': 75, 'custom_text': '1.25', 'allow_soft': True}
    if fault != 'missing': journey.check_preserved_request('before', {'ui': {'valid_choice': {'request': value}}})
    if fault == 'changed': value['allow_soft'] = False
    if fault == 'replay': journey.check_preserved_request('after', {'ui': {'valid_choice': {'request': value}}})
    result = {'operation': 'overlay-valid-fraction-soft-read', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
              'valid_choice': {'request': value}}
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}, {'stage': 'before'}]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value=result))
    journey.check_estimate = Mock()  # Independent balance arithmetic is covered by its owner.
    (tmp_path / 'after.request.json').write_text(json.dumps({'stage': 'after', 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / 'after.reply.json').exists()
    else:
        journey.step(Mock())
        assert (tmp_path / 'after.reply.json').exists()
