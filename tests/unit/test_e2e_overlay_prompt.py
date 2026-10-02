"""Shell AUTH01 context, protected input, decoder and independent attempt guards.

Parallelism: in-memory trees/doubles and private tmp_path, no live VM/display.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as a
import check_e2e_overlay_prompt as selector
from overlay_prompt import PLAN, OverlayPromptJourney
from parent_setup_qualification import OverlayPromptQualification, KioskEntryQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from ui_observations import UiObservations, OPERATION_LABELS


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
    message = Node(f'Grant {a.CHILD} 1 minute, 15 seconds and allow soft blocked apps?', 'label')
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
    elif fault == 'apps': message.name = f'Grant {a.CHILD} 1 minute, 15 seconds?'
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
    if fault in ('recipient', 'child', 'duration', 'apps'):
        assert field.get_text_iface.call_count == 1  # initial valid proof only


def proof_value():
    return {'operation': 'overlay-shell-cancel-ready', 'outcome': 'passed', 'interface': 'AT-SPI',
        'shell_prompt': {'provider': {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]},
            'child': 'fixture-child', 'approver': 'fixture-parent', 'duration_seconds': 75,
            'allow_soft': True, 'cancel_ready': True, 'same_challenge_rechecked': True,
            'rejected_proofs': list(a.SHELL_PROMPT_REFUSALS), 'challenge_id': 'a' * 64}}


@pytest.mark.parametrize('fault', [None, 'replacement', 'uncertain-submit', 'wrong-form'])
def test_real_open_sequence_rechecks_before_releasing_keyboard_input(monkeypatch, capsys, fault):
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
        with pytest.raises((a.UiError, RuntimeError)): ui.run('overlay-shell-cancel-ready', '')
        with pytest.raises(a.UiError): ui.run('overlay-shell-cancel-ready', '')
    else:
        result = ui.run('overlay-shell-cancel-ready', '')
        assert result == proof_value()
        raw = capsys.readouterr().out.encode() + (json.dumps(result) + '\n').encode()
        transport = Mock(commands=SimpleNamespace(progress=None))
        def call(*_args, on_output, **_kwargs):
            for offset in range(0, len(raw), 97): on_output(raw[offset:offset + 97])
            return raw
        transport.call.side_effect = call
        observer = UiObservations(transport)
        assert observer.observe('overlay-shell-cancel-ready') == result
        with pytest.raises(Exception, match='ui:challenge-replay'): observer.observe('overlay-shell-cancel-ready')
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


@pytest.mark.parametrize('failure', [None, 0, 1])
def test_two_owned_attempts_stop_after_first_failure(monkeypatch, failure):
    smoke = Mock(side_effect=[1 if failure == 0 else 0, 1 if failure == 1 else 0])
    monkeypatch.setattr(selector, 'smoke', smoke)
    monkeypatch.setattr(selector, 'named_input', lambda: 'owned-input')
    assert selector.main() == (0 if failure is None else 1)
    assert smoke.call_count == (1 if failure == 0 else 2)
    for call in smoke.call_args_list:
        assert call.kwargs == dict(assets='owned-input', provision_credentials=True,
                                   challenges=True, challenge_profile='overlay-prompt')


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
    result = {'operation': 'overlay-valid-fraction-soft-read', 'outcome': 'passed', 'interface': 'AT-SPI',
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
