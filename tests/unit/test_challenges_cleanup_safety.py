"""Distinct authentication proofs, terminal refusal and durable qualification."""

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
import check_e2e_challenges as check
import check_graphical_smoke as smoke
from challenges import PLAN, CHALLENGES, INVOCATIONS, ChallengesJourney
from installed_journey import InstalledJourney, matched_screens
from owned_commands import CommandError
from parent_setup_qualification import ChallengesQualification, KioskEntryQualification
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
def test_controller_challenge_checks_are_fresh_and_terminal(fault):
    transport = SimpleNamespace(call=Mock())
    ui = UiObservations(transport)

    def observe(operation, context=None):
        transport.call.return_value = json.dumps({
            'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}).encode()
        return ui.observe_challenge(operation, context) if context else ui.observe(operation)

    for identity in ('first-login', 'second-login'):
        observe('gdm-focused')
        first = {'id': identity, 'role': 'parent', 'surface': 'gdm', 'check': 'qualified'}
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
    journey.ui = SimpleNamespace(observe_challenge=Mock(
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
