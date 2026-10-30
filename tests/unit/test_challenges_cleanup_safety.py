"""Distinct authentication proofs, terminal refusal and durable qualification."""

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
import check_e2e_challenges as check
import check_e2e_fresh_child_allowed as child_check
import check_e2e_unlock as denied_check
import check_graphical_smoke as smoke
from challenges import PLAN, CHALLENGES, INVOCATIONS, ChallengesJourney
from fresh_child_allowed import PLAN as CHILD_PLAN, FreshChildAllowedJourney
from fresh_child_denied import PLAN as DENIED_PLAN, FreshChildDeniedJourney
from installed_journey import InstalledJourney, matched_screens
from owned_commands import CommandError
from parent_setup_qualification import ChallengesQualification, KioskEntryQualification, FreshChildAllowedQualification
from parent_setup_qualification import FreshChildDeniedQualification
from private_artifacts import EvidenceError
from tests.support.perl import run_perl
from ui_observations import UiObservations


def test_fixed_dispatch_and_registered_operations(monkeypatch):
    context = SimpleNamespace()
    assert issubclass(ChallengesQualification, KioskEntryQualification)
    assert isinstance(ChallengesQualification.journey(context, Mock()), ChallengesJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True, 'challenges': True}]
    for tag in PLAN.screen_tags.values():
        if tag.startswith('ui:'):
            assert tag[3:] in accessible_ui.OPERATIONS
    for options in ({}, {'assets': check.ASSETS, 'provision_credentials': True,
                         'repeated_operations': True}):
        with pytest.raises(CommandError, match='challenges-prerequisites'):
            smoke.main(challenges=True, **options)


def test_fresh_child_dispatch_and_nondefault_identity(monkeypatch):
    context = SimpleNamespace()
    assert isinstance(FreshChildAllowedQualification.journey(context, Mock()), FreshChildAllowedJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    calls = []
    monkeypatch.setattr(child_check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert child_check.main() == 0
    assert calls == [{'assets': child_check.named_input(vm_source=True), 'provision_credentials': True,
                     'challenges': True, 'challenge_profile': 'fresh-child'}]
    assert CHILD_PLAN.challenge_at('fresh-child-recipient-rechecked')['role'] == 'child'
    for tag in CHILD_PLAN.screen_tags.values():
        if tag.startswith('ui:'):
            assert tag[3:] in accessible_ui.OPERATIONS
    with pytest.raises(CommandError, match='challenge-profile'):
        smoke.main(challenge_profile='fresh-child')
    with pytest.raises(EvidenceError, match='challenge-plan'):
        replace(CHILD_PLAN, challenges={**CHILD_PLAN.challenges,
            'child-login': ('other-child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')})


def test_denied_child_dispatch_and_declared_result(monkeypatch):
    assert isinstance(FreshChildDeniedQualification.journey(SimpleNamespace(), Mock()),
                      FreshChildDeniedJourney)
    calls = []
    monkeypatch.setattr(denied_check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert denied_check.main() == 0
    assert calls == [{'assets': denied_check.named_input(vm_source=True), 'provision_credentials': True,
                     'challenges': True, 'challenge_profile': 'fresh-child-denied'}]
    assert DENIED_PLAN.challenge_at('fresh-child-recipient-rechecked')['role'] == 'child'
    for tag in DENIED_PLAN.screen_tags.values():
        if tag.startswith('ui:'):
            assert tag[3:] in accessible_ui.OPERATIONS


@pytest.mark.parametrize('fault', ['', 'allowance-configured', 'switch-user', 'gdm-switched',
    'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked', 'fresh-denied',
    'denied-return-ready', 'denied-return-state', 'denied-returned'])
@pytest.mark.parametrize('destination', ['account-list', 'child-prompt'])
def test_actual_denied_child_worker_preserves_denial_and_stops_before_escape(fault, destination):
    program = (PERL.replace('onpc_challenges::run(', 'onpc_challenges::fresh_child_denied(')
        .replace('(?:list|greeter|focused)', '(?:list|greeter|focused|opened)')
        .replace('first-login', 'parent-login').replace('third-login', 'new-login')
        .replace('my $reply = {observed => $stage};',
                 'my $reply = {observed => $stage}; $reply->{gdm_return_state} = "' + destination
                 + '" if $stage eq "denied-return-state";'))
    raw = run_perl(program, fault, json.dumps(DENIED_PLAN.invocations),
                   json.dumps(DENIED_PLAN.challenges)).stdout
    assert 'fixture-only-canary' not in raw
    result = json.loads(raw)
    assert bool(result['ok']) == (not fault), result
    assert result['retry'] == result['captured'] == result['after_failure'] == 0
    assert len(result['events']) == result['before']
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(DENIED_PLAN.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if fault in ('fresh-denied', 'denied-return-ready'):
        assert result['events'][-1] == ['stage', fault]
        assert result['events'].count(['key', 'esc']) == 1  # wrong-recipient harness only
    if not fault:
        assert result['events'].count(['password']) == 2
        assert result['events'].count(['key', 'esc']) == (3 if destination == 'child-prompt' else 2)
        assert result['events'][-1] == ['off']


@pytest.mark.parametrize('binding', [
    ('child', 'recipient-qualified', 'recipient-rechecked'),
    ('parent', 'recipient-rechecked', 'recipient-qualified'),
    ('parent', 'recipient-qualified', 'second-recipient-rechecked'),
    ('parent', 'missing', 'recipient-rechecked'),
    ('other-child', 'recipient-qualified', 'recipient-rechecked'),
])
def test_challenge_plan_rejects_unbound_mixed_or_reordered_proofs(binding):
    with pytest.raises(EvidenceError, match='challenge-plan'):
        replace(PLAN, challenges={**CHALLENGES, 'first-login': binding})


@pytest.mark.parametrize('fault', ['', 'stale-id', 'role', 'surface', 'intervening', 'replay',
                                   'missing-first', 'transport'])
@pytest.mark.parametrize('role', ['parent', 'child'])
def test_controller_challenge_checks_are_fresh_and_terminal(fault, role):
    transport = SimpleNamespace(call=Mock())
    ui = UiObservations(transport)

    def observe(operation, context=None):
        if role == 'child':
            operation = operation.replace('gdm-parent-recipient', 'gdm-child-recipient')
            operation = operation.replace('gdm-focused', 'gdm-child-focused')
        transport.call.return_value = json.dumps({
            'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}).encode()
        return ui.observe_challenge(operation, context) if context else ui.observe(operation)

    for identity in ('first-login', 'second-login'):
        observe('gdm-focused')
        first = {'id': identity, 'role': role, 'surface': 'gdm', 'check': 'qualified'}
        second = {**first, 'check': 'rechecked'}
        if identity == 'second-login' and fault == 'replay':
            first['id'] = 'first-login'
        if fault != 'missing-first':
            if identity == 'second-login' and fault == 'replay':
                with pytest.raises(EvidenceError): observe('gdm-parent-recipient', first)
                break
            observe('gdm-parent-recipient', first)
        if fault == 'stale-id': second['id'] = 'another-login'
        if fault == 'role': second['role'] = 'other-child'
        if fault == 'surface': second['surface'] = 'polkit'
        if fault == 'intervening': observe('gdm-focused')
        if fault == 'transport': transport.call.side_effect = RuntimeError('observation failed')
        if fault and fault != 'replay':
            with pytest.raises((EvidenceError, RuntimeError)):
                observe('gdm-parent-recipient-rechecked', second)
            break
        observe('gdm-parent-recipient-rechecked', second)
    if fault:
        with pytest.raises(EvidenceError, match='previous-failure'):
            observe('gdm-parent-recipient', first)
    else:
        assert transport.call.call_count == 6


PERL = r'''
use strict;
use warnings;
use JSON::PP;
our $fault = shift @ARGV;
our @events;
our $passwords = 0;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub get_var { 1 }
sub get_required_var { push @main::events, ['variable', $_[0]]; 'fixture-only-canary' }
sub type_password {
    die 'options' unless @_ == 1 && $_[0] eq 'fixture-only-canary';
    push @main::events, ['password'];
    $main::passwords++;
    die 'private fixture-only-canary' if $main::fault eq 'typing';
}
sub send_key { push @main::events, ['key', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['off'] }
sub check_shutdown { 1 }
package Console;
sub disable { }
package main;
require onpc_challenges;
my $declaration = decode_json(shift @ARGV);
my $bindings = decode_json(shift @ARGV);
my $old;
my $exchange = sub {
    my ($stage) = @_;
    push @events, ['stage', $stage];
    die 'private fixture-only-canary' if $fault eq $stage;
    my $reply = {observed => $stage};
    $reply->{ui_focused} = JSON::PP::true if $stage =~ /(?:list|greeter|focused)$/;
    for my $id (keys %$bindings) {
        my ($role, $first, $second) = @{$bindings->{$id}};
        next unless $stage eq $first || $stage eq $second;
        $reply->{challenge} = {id => $id, role => $role, surface => 'gdm',
            check => $stage eq $first ? 'qualified' : 'rechecked'};
        if ($stage eq 'second-recipient-rechecked') {
            $reply = $old if $fault eq 'stale';
            $reply->{challenge}{id} = 'first-login' if $fault eq 'mixed';
            $reply->{challenge}{role} = 'other-child' if $fault eq 'role';
            $reply->{challenge}{surface} = 'lock' if $fault eq 'surface';
            delete $reply->{challenge} if $fault eq 'missing';
        }
        $old = $reply if $stage eq 'recipient-rechecked';
    }
    return $reply;
};
my $ok = eval { onpc_challenges::run($exchange, $declaration, $bindings); 1 };
my $error = $@;
# After success or failure a new journey cannot recycle a challenge identity.
my $j = onpc_journey->new(exchange => $exchange, prefix => 'retry', review => 0);
$j->declare_invocations(['recipient-qualified', 'recipient-rechecked']);
$j->declare_challenges({'first-login' => ['parent', 'recipient-qualified', 'recipient-rechecked']});
my $before = scalar @events;
my $retry = eval { onpc_password::enter_gdm_challenge($j, 'first-login'); 1 };
my $fresh = onpc_journey->new(exchange => $exchange, prefix => 'fresh', review => 0);
$fresh->declare_invocations(['recipient-qualified', 'recipient-rechecked']);
$fresh->declare_challenges({'third-login' => ['parent', 'recipient-qualified', 'recipient-rechecked']});
my $after_failure = eval { onpc_password::enter_gdm_challenge($fresh, 'third-login'); 1 };
my $captured = eval { onpc_password::capture_before_authentication(); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $error, events => \@events,
    before => $before, retry => $retry ? 1 : 0, captured => $captured ? 1 : 0,
    after_failure => $after_failure ? 1 : 0});
'''


# Scope and binding interact in the authorization allowlist. Check that finite
# table once; exercise shared sealing/refusal faults only on the base approval.
@pytest.mark.parametrize('fault,binding,credential,scope', [
    *[('', binding, 'fixture-only-canary', scope)
      for scope in ('base', 'flow', 'package-removal', 'revoke-cancel', 'revocation', 'unknown',
                    'confinement-usability', 'confinement-usability-rejection',
                    'kiosk-service-recovery')
      for binding in ('approval', 'rejection')],
    *[(fault, 'approval', 'fixture-only-canary', 'base')
      for fault in ('qualified', 'rechecked', 'typing', 'capture', 'review', 'stale', 'missing')],
    ('', 'approval', 'onpc-wrong-fixture-password', 'base'),
    ('', 'rejection', 'onpc-wrong-fixture-password', 'base'),
    ('typing', 'rejection', 'fixture-only-canary', 'base'),
    ('', 'long-request', 'fixture-only-canary', 'natural-access'),
    ('', 'approval', 'fixture-only-canary', 'natural-access'),
    ('', 'rejection', 'fixture-only-canary', 'natural-access'),
    ('', 'approval', 'fixture-only-canary', 'grant-only-profile'),
    ('', 'request-120', 'fixture-only-canary', 'profile-request'),
    ('', 'request-120', 'fixture-only-canary', 'switch-user-expiry-parent-profile-request'),
    ('', 'request-120', 'fixture-only-canary', 'switch-user-expiry-parent'),
    ('', 'request-120', 'fixture-only-canary', 'unknown'),
    ('', 'request-120', 'fixture-only-canary', 'grant-only-profile'),
])
def test_mate_secret_is_single_use_sealed_and_terminal_on_uncertainty(fault, binding, credential, scope):
    program = r'''
use strict; use warnings; use JSON::PP;
our $fault = shift @ARGV; our @events;
our $binding = shift @ARGV; our $credential = shift @ARGV;
our $scope = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { $main::fault eq 'capture' ? 0 : 1 }
sub get_required_var { push @main::events, 'read'; $main::credential }
sub type_password {
    push @main::events, 'type';
    die 'wrong credential selection' unless ($_[0] ne $main::credential) == ($main::binding eq 'rejection');
    die 'fixture-only-canary' if $main::fault eq 'typing';
}
package main;
require onpc_journey; require onpc_password;
my $journey = onpc_journey->new(prefix => $scope eq 'profile-request' ? 'grant-only-profile' : $scope eq 'switch-user-expiry-parent-profile-request' ? 'switch-user-expiry-parent' : $scope eq 'flow' ? 'kiosk-approval-flow' : $scope eq 'base' ? 'kiosk-' . $binding : $scope eq 'confinement-usability-rejection' ? 'confinement-usability' : $scope, review => ($fault eq 'review' ? 1 : 0),
    exchange => sub {
        my ($stage) = @_;
        push @events, $stage;
        die 'fixture-only-canary' if $stage eq $binding . '-' . $fault;
        return {} if $fault eq 'missing';
        return {observed => $fault eq 'stale' ? $binding . '-qualified' : $stage};
    });
$journey = $journey->scope('rejection') if $scope eq 'confinement-usability-rejection';
$journey = $journey->scope('profile-request')
    if $scope eq 'profile-request' || $scope eq 'switch-user-expiry-parent-profile-request';
my @args = $binding eq 'rejection' ? ($journey, 'wrong') :
    $binding =~ /\A(?:long-request|request-120)\z/ ? ($journey, $binding) : ($journey);
my $ok = eval { onpc_password::enter_kiosk_mate_password(@args); 1 };
my $error = "$@"; my $before = scalar @events;
my $retry = eval { onpc_password::enter_kiosk_mate_password(@args); 1 };
my $capture = eval { onpc_password::capture_before_authentication(); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $error, before => $before,
    retry => $retry ? 1 : 0, capture => $capture ? 1 : 0, events => \@events});
'''
    raw = run_perl(program, fault, binding, credential, scope).stdout
    assert 'fixture-only-canary' not in raw
    value = json.loads(raw)
    allowed = (scope in ('base', 'flow') or
               scope in ('package-removal', 'revoke-cancel', 'revocation', 'confinement-usability',
                         'kiosk-service-recovery')
               and binding == 'approval' or
               scope == 'natural-access' and binding == 'long-request' or
               scope in ('profile-request', 'switch-user-expiry-parent-profile-request')
               and binding == 'request-120' or
               scope == 'grant-only-profile' and binding == 'approval' or
               scope == 'confinement-usability-rejection' and binding == 'rejection')
    assert bool(value['ok']) == (allowed and not fault), value
    assert value['retry'] == value['capture'] == 0
    assert len(value['events']) == value['before']
    assert value['events'].count('type') == (1 if allowed and fault in ('', 'typing') else 0)
    if not allowed:
        assert value['events'] == []
    elif not fault:
        prefix = ('rejection-' if scope == 'confinement-usability-rejection' else
                  'profile-request-' if scope in ('profile-request', 'switch-user-expiry-parent-profile-request') else '')
        binding = 'approval' if binding in ('long-request', 'request-120') else binding
        assert value['events'] == [prefix + binding + '-qualified', prefix + binding + '-rechecked', 'read', 'type']


@pytest.mark.parametrize('fault', ['', 'qualified', 'rechecked', 'typing', 'capture', 'review', 'cancel-authority', 'stale'])
@pytest.mark.parametrize('rejection', [False, True])
def test_shell_secret_is_single_use_sealed_and_terminal_on_uncertainty(fault, rejection):
    program = r'''
use strict; use warnings; use JSON::PP;
our $fault = shift @ARGV; our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { $main::fault eq 'capture' ? 0 : 1 }
sub get_required_var { push @main::events, 'read'; 'fixture-only-canary' }
sub type_password { push @main::events, 'type'; die 'fixture-only-canary' if $main::fault eq 'typing'; }
package main;
require onpc_journey; require onpc_password;
my $journey = onpc_journey->new(prefix => $fault eq 'cancel-authority' ? 'overlay-prompt' : 'overlay-approved-exit',
    review => $fault eq 'review' ? 1 : 0, exchange => sub {
        my ($stage) = @_; push @events, $stage;
        die 'fixture-only-canary' if $stage eq 'approval-' . $fault;
        return {observed => $fault eq 'stale' ? 'approval-qualified' : $stage};
    });
my $ok = eval { onpc_password::enter_overlay_shell_password($journey); 1 };
my $error = "$@"; my $before = scalar @events;
my $retry = eval { onpc_password::enter_overlay_shell_password($journey); 1 };
my $capture = eval { onpc_password::capture_before_authentication(); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $error, before => $before,
    retry => $retry ? 1 : 0, capture => $capture ? 1 : 0, events => \@events});
'''
    if rejection:
        program = (program.replace('overlay-approved-exit', 'overlay-rejection')
            .replace('approval-', 'another-')
            .replace('enter_overlay_shell_password($journey)', "enter_overlay_shell_password($journey, 'wrong', 'another')")
            .replace("push @main::events, 'type';", "die 'wrong-input' unless $_[0] eq 'onpc-wrong-fixture-password'; push @main::events, 'type';"))
    raw = run_perl(program, fault).stdout
    assert 'fixture-only-canary' not in raw
    value = json.loads(raw)
    assert bool(value['ok']) == (not fault), value
    assert value['retry'] == value['capture'] == 0
    assert len(value['events']) == value['before']
    assert value['events'].count('type') == (1 if fault in ('', 'typing') else 0)


@pytest.mark.parametrize('fault', ['', 'stale', 'mixed', 'role', 'surface', 'missing', 'typing',
    'recipient-qualified', 'recipient-rechecked', 'second-recipient-qualified',
    'second-recipient-rechecked'])
def test_actual_worker_two_authentications_and_terminal_refusal(fault):
    raw = run_perl(PERL, fault, json.dumps(INVOCATIONS), json.dumps(CHALLENGES)).stdout
    assert 'fixture-only-canary' not in raw
    result = json.loads(raw)
    assert bool(result['ok']) == (not fault), result
    assert not result['retry'] and not result['captured']
    assert not result['after_failure']
    assert len(result['events']) == result['before']
    if not fault:
        stages = [event[1] for event in result['events'] if event[0] == 'stage']
        assert stages == list(PLAN.screen_tags)
        assert result['events'].count(['password']) == 2
        assert result['events'][-1] == ['off']
        assert result['events'].index(['stage', 'gdm-logged-out']) < result['events'].index(
            ['stage', 'second-recipient-qualified'])
    else:
        assert ['off'] not in result['events']
        assert result['events'].count(['password']) <= 1


@pytest.mark.parametrize('fault', ['', 'stale', 'mixed', 'role', 'surface', 'missing', 'typing',
    'allowance-configured', 'switch-user', 'gdm-switched', 'wrong-refused',
    'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked', 'fresh-desktop'])
def test_actual_fresh_child_worker_stops_at_failure_and_uses_child_secret(fault):
    program = (PERL.replace('onpc_challenges::run(', 'onpc_challenges::fresh_child_allowed(')
        .replace('(?:list|greeter|focused)', '(?:list|greeter|focused|opened)')
        .replace('second-recipient-rechecked', 'fresh-child-recipient-rechecked')
        .replace('first-login', 'parent-login').replace('third-login', 'new-login'))
    raw = run_perl(program, fault, json.dumps(CHILD_PLAN.invocations),
                   json.dumps(CHILD_PLAN.challenges)).stdout
    assert 'fixture-only-canary' not in raw
    result = json.loads(raw)
    assert bool(result['ok']) == (not fault), result
    assert result['retry'] == result['captured'] == result['after_failure'] == 0
    assert len(result['events']) == result['before']
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    if not fault:
        assert stages == list(CHILD_PLAN.screen_tags)
        assert [event for event in result['events'] if event[0] == 'variable'] == [
            ['variable', '_SECRET_ONPC_PARENT_PASSWORD'], ['variable', '_SECRET_ONPC_CHILD_PASSWORD']]
        assert result['events'].count(['password']) == 2
        assert result['events'][-1] == ['off']
    else:
        assert ['off'] not in result['events']
        if fault in CHILD_PLAN.screen_tags:
            assert stages == list(CHILD_PLAN.screen_tags)[:list(CHILD_PLAN.screen_tags).index(fault) + 1]
        if fault != 'fresh-desktop':
            assert result['events'].count(['password']) <= 1


@pytest.mark.parametrize('route', ['legacy', 'leaf', 'explicit-leaf'])
def test_unbound_or_replayed_leaf_failure_blocks_even_a_new_challenge(route):
    raw = run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub current_console { 'sut' }
sub get_var { 1 }
sub get_required_var { 'fixture-only-canary' }
sub type_password { push @main::events, 'password' }
package main;
require onpc_password;
require onpc_journey;
my $route = shift @ARGV;
my $j = onpc_journey->new(prefix => 'unit', review => 0, exchange => sub {
    my ($stage) = @_;
    push @events, $stage;
    return {observed => $stage};
});
my $ok = eval {
    if ($route eq 'legacy') {
        onpc_password::enter_parent_gdm_password($j);
        onpc_password::enter_parent_gdm_password($j);
    } else {
        my $proof = $j->seen('recipient-rechecked');
        my $copy = {%$proof};
        $route eq 'leaf' ? onpc_password::type_fixture_secret('parent', $j, $copy)
            : onpc_password::type_fixture_secret('parent', $j, $proof, 'unbound');
    }
    1;
};
my $before = scalar @events;
$j->declare_invocations(['fresh-first', 'fresh-second']);
$j->declare_challenges({'fresh' => ['parent', 'fresh-first', 'fresh-second']});
my $fresh = eval { onpc_password::enter_gdm_challenge($j, 'fresh'); 1 };
print encode_json({ok => $ok ? 1 : 0, fresh => $fresh ? 1 : 0,
                  before => $before, events => \@events});
''', route).stdout
    result = json.loads(raw)
    assert not result['ok'] and not result['fresh']
    assert len(result['events']) == result['before']
    assert result['events'].count('password') == (1 if route == 'legacy' else 0)


@pytest.mark.parametrize('failure', ['observation', 'durability', 'guard'])
def test_challenge_reply_requires_observation_storage_and_final_guard(tmp_path, failure):
    stage = 'second-recipient-rechecked'
    context = SimpleNamespace(directory=tmp_path)
    progress = Mock(side_effect=OSError('store') if failure == 'durability' else None)
    journey = InstalledJourney(context, progress, PLAN)
    journey.steps = [{'stage': name} for name in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'boot'}))
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe_challenge=Mock(
        side_effect=EvidenceError('proof') if failure == 'observation' else None,
        return_value={'operation': PLAN.screen_tags[stage][3:], 'outcome': 'passed'}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    guard = Mock(side_effect=[None, None, RuntimeError('lost owner')]
                 if failure == 'guard' else None)
    with pytest.raises((EvidenceError, OSError, RuntimeError)):
        journey.step(guard)
    assert not (tmp_path / (stage + '.reply.json')).exists()
    with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())


def test_qualification_assertion_is_durable_before_next_phase():
    q = object.__new__(ChallengesQualification)
    q.result = {}
    events = []
    q.checkpoint = lambda event: events.append((event, json.loads(json.dumps(q.result))))
    observed = {'stage': 'gdm-logged-out', 'ui': {'outcome': 'passed'},
                'assertion': {'id': 'logout-complete', 'phase': 'step-1'}}
    q.record_progress(SimpleNamespace(plan=PLAN, steps=[observed]), 'gdm-logged-out', observed)
    assert [event for event, _ in events] == ['stage-observed', 'assertion', 'phase-started']
    assert [value['active_phase'] for _, value in events] == ['step-1', 'step-1', 'step-2']


@pytest.mark.parametrize('fault', ['', 'missing', 'stale', 'wrong-role'])
def test_reconciliation_binds_each_durable_proof_to_its_challenge(tmp_path, fault):
    observations = []
    for stage, tag in PLAN.screen_tags.items():
        kind, operation = tag.split(':', 1)
        observed = {'stage': stage, kind: {'operation': operation, 'outcome': 'passed'}}
        if PLAN.challenge_at(stage):
            observed['challenge'] = PLAN.challenge_at(stage)
        if stage == 'second-recipient-rechecked':
            if fault == 'missing': del observed['challenge']
            if fault == 'stale': observed['challenge']['id'] = 'first-login'
            if fault == 'wrong-role': observed['challenge']['role'] = 'other-child'
        observations.append(observed)
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({
        'result': 'ok', 'details': [{'title': PLAN.prefix + '-' + stage, 'result': 'ok'}
                                   for stage in PLAN.screen_tags]}))
    if fault:
        with pytest.raises(EvidenceError, match='challenge-evidence'):
            matched_screens(tmp_path, PLAN, observations)
    else:
        assert len(matched_screens(tmp_path, PLAN, observations)) == len(PLAN.screen_tags)
