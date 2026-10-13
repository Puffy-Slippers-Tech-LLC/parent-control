"""TIME04 private journey/worker refusals; no live VM, desktop or settings.

Parallelism: pytest-private replies, process-local clocks/recorder doubles and
bounded waited Perl children. No shared cache, socket, bus or cleanup owner.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import accessible_ui
import check_e2e_natural_expiry as selector
import check_graphical_smoke as smoke
import natural_expiry
from countdown import CountdownSample
from installed_journey import record_installed_journey
from natural_expiry import NaturalExpiryJourney, PLAN
from owned_commands import CommandError
from parent_setup_qualification import NaturalExpiryQualification, KioskEntryQualification
from private_artifacts import EvidenceError
from tests.support.perl import run_perl
from tests.support.paths import ROOT


ACTIVITY = {'binding': 'native-primary', 'pid': 123, 'endpoint': [':1.50', '/accessible/1'],
            'state': {'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft',
                      'score': 'Moves: 0; token: 0'}}


def countdown_value():
    return {'operation': 'child-countdown-present', 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider',
            'countdown': {'child': 'fixture-child', 'surface': 'desktop', 'present': True,
                          'text': '00:01', 'observed_monotonic_ns': 20_000_000_000,
                          'stable_ms': 0},
            'countdown_read_bounds': [100_000_000_000, 101_000_000_000]}


def test_selector_and_real_recorder_construct_the_fixed_installed_journey(monkeypatch, tmp_path):
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0
    assert run.call_args.kwargs == {'assets': selector.named_input(fixture_source=True),
        'provision_credentials': True, 'challenges': True, 'challenge_profile': 'natural-expiry'}
    with pytest.raises(CommandError, match='challenges-prerequisites'):
        smoke.main(challenges=True, challenge_profile='natural-expiry')
    assert NaturalExpiryQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    context = SimpleNamespace(directory=tmp_path)
    assert NaturalExpiryQualification.journey(context, Mock()).plan is PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock(), recorder=MagicMock())
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is NaturalExpiryJourney and journey.plan is PLAN
        assert set(journey.actions) == {'native-verify', 'natural-expiry'}
        raise EvidenceError('fixture:worker-stop')
    context.run_worker = worker
    with pytest.raises(EvidenceError, match='fixture:worker-stop'):
        record_installed_journey(context.recorder, context, PLAN, journey_type=NaturalExpiryJourney)


@pytest.mark.parametrize('refuse', ['', 'setup-detached'])
def test_actual_dispatch_requires_detached_setup_before_natural_activity(monkeypatch, refuse):
    source = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    monkeypatch.setenv('ONPC_TEST_REFUSE', refuse)
    program = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'basetest.pm'} = 1; }
package basetest;
sub new { bless {}, shift }
package testapi;
sub import { no strict 'refs'; *{caller() . '::console'} = \&console; }
sub console { push @main::events, ['console', $_[0]]; bless {}, 'Console' }
package Console;
sub disable { push @main::events, ['disabled']; }
package main;
my $source = decode_json(SOURCE_JSON);
while ($source =~ /use (onpc_\w+)/g) { $INC{"$1.pm"} = 1; }
eval 'package DispatchProbe;' . $source;
die $@ if $@;
{
    no warnings 'redefine';
    *DispatchProbe::exchange = sub {
        push @events, ['stage', $_[0]];
        die 'fixture:refused' if $_[0] eq ($ENV{ONPC_TEST_REFUSE} // '');
        return {natural_expiry => JSON::PP::true, invocations => ['finite'],
                challenge_bindings => {login => ['child', 'one', 'two']}};
    };
    *onpc_challenges::natural_expiry = sub {
        push @events, ['worker', $_[1], $_[2]];
        die 'fixture:callback' unless ref($_[0]) eq 'CODE';
    };
}
my $ok = eval { DispatchProbe::run(); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''
    literal = "'" + json.dumps(source).replace('\\', '\\\\').replace("'", "\\'") + "'"
    result = json.loads(run_perl(program.replace('SOURCE_JSON', literal)).stdout)
    expected = [['stage', 'ready'], ['console', 'sut'], ['disabled'], ['stage', 'setup-detached']]
    if not refuse:
        expected.append(['worker', ['finite'], {'login': ['child', 'one', 'two']}])
    assert result['events'] == expected
    assert bool(result['ok']) is (not refuse), result['error']


@pytest.mark.parametrize('fault', [None, 'missing-balance', 'replay', 'balance-mismatch',
                                 'missing-activity', 'helper-refusal', 'durability'])
def test_natural_lock_action_uses_immutable_entry_and_precedes_durable_reply(monkeypatch, tmp_path, fault):
    stage = 'natural-expiry'
    progress = Mock(side_effect=OSError('fixture:storage') if fault == 'durability' else None)
    journey = NaturalExpiryJourney(SimpleNamespace(directory=tmp_path), progress)
    journey.steps = [{'stage': name} for name in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.balance = (120, 1, 10_000_000_000)
    if fault == 'missing-balance':
        journey.balance = None
    if fault == 'balance-mismatch':
        journey.balance = (600, 1, 10_000_000_000)
    value = countdown_value()
    if fault == 'replay':
        journey.initial_countdown = CountdownSample.from_ui(value, boot_sha256=journey.boot)
    if fault != 'missing-activity':
        activity = deepcopy(ACTIVITY)
        journey.check_activity('activity-capture', {'ui': {'activity': activity}})
        activity['state']['draft'] = 'mutated caller object'
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value=value))
    result = {'initial_countdown': value['countdown'], 'lock': {'locked': True},
              'elapsed_interval_seconds': [118, 120], 'activity_actions': 3}
    helper = Mock(side_effect=EvidenceError('fixture:observation-gap')
                  if fault == 'helper-refusal' else None, return_value=result)
    monkeypatch.setattr(natural_expiry, 'await_natural_expiry', helper)
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            journey.step(lambda: 1000)
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(lambda: 1000)
        if fault in ('missing-balance', 'balance-mismatch', 'missing-activity', 'replay'):
            helper.assert_not_called()
    else:
        journey.step(lambda: 1000)
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['fixture'] == result
        assert journey.natural_expiry_result == result
        previous, activity = helper.call_args.args[2:]
        assert type(previous) is CountdownSample
        assert previous.countdown.text == '00:01'
        assert activity.state[0] == 'ONPC fixture draft'


WORKER = r'''
use strict; use warnings; use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_password.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['title', $_[0]]; }
sub send_key { push @main::events, ['input', $_[0]]; }
sub power { }
sub check_shutdown { 1 }
sub console { bless {}, 'Console' }
package Console;
sub disable { }
package onpc_gdm;
sub reattach_functional { }
sub sign_in_challenge {
 my ($j, $id, $greeter, $focused, $desktop) = @_;
 my $child = $id eq 'child-login';
 $j->invoke($greeter); $j->invoke($focused);
 $j->invoke($child ? 'fresh-child-recipient-qualified' : 'recipient-qualified');
 $j->invoke($child ? 'fresh-child-recipient-rechecked' : 'recipient-rechecked');
 return $j->invoke($desktop);
}
package main;
require onpc_challenges;
my $plan = decode_json($ARGV[0]);
my $exchange = sub {
 push @events, ['stage', $_[0]];
 die 'fixture:refused' if $_[0] eq ($ENV{ONPC_TEST_REFUSE} // '');
 return {observed => $_[0], ui_focused => JSON::PP::true};
};
my $ok = eval { onpc_challenges::natural_expiry($exchange, $plan->{invocations}, $plan->{challenges}); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''


def test_actual_worker_order_and_every_refusal_stop_before_later_input(monkeypatch):
    args = json.dumps({'invocations': PLAN.invocations, 'challenges': PLAN.challenges})
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(WORKER, args).stdout)
    assert success['ok'], success['error']
    events = success['events']
    assert [event[1] for event in events if event[0] == 'stage'] == list(PLAN.screen_tags)
    assert [event[1] for event in events if event[0] == 'title'] == [
        *(PLAN.prefix + '-' + stage for stage in PLAN.screen_tags), 'shutdown']
    assert [event for event in events if event[0] == 'input'] == [['input', 'shift']]
    assert events.index(['stage', 'lock-input-ready']) < events.index(['input', 'shift']) < events.index(
        ['stage', 'lock-result'])
    for stage in PLAN.screen_tags:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        refused = json.loads(run_perl(WORKER, args).stdout)
        assert not refused['ok'] and 'fixture:refused' in refused['error']
        assert refused['events'] == events[:events.index(['stage', stage]) + 1]
    assert all(tag[3:] in accessible_ui.OPERATIONS for tag in PLAN.screen_tags.values()
               if tag.startswith('ui:'))


@pytest.mark.parametrize('fault', ['missing-final-stage', 'wrong-child', 'missing-challenge'])
def test_worker_refuses_invalid_plan_before_any_guest_stage(fault):
    invocations = list(PLAN.invocations)
    challenges = {key: list(value) for key, value in PLAN.challenges.items()}
    if fault == 'missing-final-stage':
        invocations.pop()
    elif fault == 'wrong-child':
        challenges['child-login'][0] = 'other-child'
    else:
        challenges.pop('child-login')
    result = json.loads(run_perl(WORKER, json.dumps({
        'invocations': invocations, 'challenges': challenges})).stdout)
    assert not result['ok'] and 'natural-expiry:plan' in result['error']
    assert result['events'] == []
