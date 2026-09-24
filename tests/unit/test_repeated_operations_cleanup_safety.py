"""Repeated invocation identity, durable assertions and fixed VM dispatch."""

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_give_repeated_public_operations_distinct_stages as check
import check_graphical_smoke as smoke
from installed_journey import InstalledJourney, matched_screens
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, RepeatedOperationsQualification
from private_artifacts import EvidenceError
from repeated_operations import INVOCATIONS, PLAN, RepeatedOperationsJourney
from tests.support.perl import run_perl


def test_fixed_dispatch_requires_assets_and_exclusive_route(monkeypatch):
    context = SimpleNamespace()
    assert issubclass(RepeatedOperationsQualification, KioskEntryQualification)
    assert isinstance(RepeatedOperationsQualification.journey(context, Mock()),
                      RepeatedOperationsJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'repeated_operations': True}]
    for options in ({}, {'assets': check.ASSETS, 'provision_credentials': True,
                         'parent_about': True}):
        with pytest.raises(CommandError, match='repeated-operations-prerequisites'):
            smoke.main(repeated_operations=True, **options)


@pytest.mark.parametrize('changes', [
    {'invocations': ('baseline-first', 'baseline-first')},
    {'invocations': ('missing',)},
    {'invocations': tuple(reversed(INVOCATIONS))},
    {'assertions_after': {'missing': 'first-return'}},
    {'assertions_after': {'return-first': 'same', 'return-second': 'same'}},
    {'screen_tags': {'../outside': 'ui:parent-selected'}},
])
def test_invalid_declarations_refuse_before_worker(changes):
    with pytest.raises(EvidenceError):
        replace(PLAN, **changes)


@pytest.mark.parametrize('fault', ['', 'duplicate', 'missing', 'stale', 'reordered', 'exchange',
                                   'unfinished'])
def test_actual_worker_invocations_are_finite_ordered_and_terminal_on_failure(fault):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power'] }
sub check_shutdown { 1 }
package Console;
sub disable { }
package main;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'repeat', review => 0, exchange => sub {
    my ($stage) = @_;
    push @events, ['exchange', $stage];
    die 'uncertain exchange' if $fault eq 'exchange';
    return {} if $fault eq 'missing';
    return {observed => 'first'} if $fault eq 'stale';
    return {observed => $stage};
});
$journey->declare_invocations(['first', 'second']);
my $ok = eval {
    $journey->invoke($fault eq 'reordered' ? 'second' : 'first');
    $journey->invoke($fault eq 'duplicate' ? 'first' : 'second') unless $fault eq 'unfinished';
    $journey->finish();
    1;
};
my $error = $@;
my $retry = eval { $journey->invoke('second'); 1 };
my $retry_error = $@;
my $seen = eval { $journey->seen('second'); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $error,
    retry => $retry ? 1 : 0, retry_error => $retry_error, seen => $seen ? 1 : 0,
    events => \@events});
''', fault).stdout)
    assert bool(result['ok']) == (not fault), result
    assert not result['retry']
    assert not result['seen']
    if fault:
        assert 'previous-failure' in result['retry_error']
        assert ['power'] not in result['events']
    assert result['events'].count(['exchange', 'first']) <= 1
    assert result['events'].count(['exchange', 'second']) <= 1


def test_actual_slice_consumes_each_proof_and_uses_declared_ids():
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub console { bless {}, 'Console' }
sub power { push @main::events, 'off' }
sub check_shutdown { 1 }
package Console;
sub disable { }
package main;
require onpc_repeated_operations;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { $_[0]->seen('parent-selected') };
my $declared = decode_json(shift @ARGV);
onpc_repeated_operations::run(sub {
    my ($stage) = @_;
    push @events, $stage;
    return {observed => $stage};
}, $declared);
print encode_json(\@events);
''', json.dumps(INVOCATIONS)).stdout)
    assert result == ['parent-selected', *INVOCATIONS, 'off']


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'reordered', 'stale'])
def test_reconciliation_rejects_invalid_repeated_results(tmp_path, fault):
    stages = list(PLAN.screen_tags)
    observations = [{'stage': stage, 'ui': {'operation': PLAN.screen_tags[stage][3:],
                                           'outcome': 'passed'}} for stage in stages]
    if fault == 'missing':
        observations.pop()
    elif fault == 'duplicate':
        observations.append(observations[-1])
    elif fault == 'reordered':
        stages[-1], stages[-2] = stages[-2], stages[-1]
    else:
        observations[-1] = {**observations[-1], 'stage': 'return-first'}
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({
        'result': 'ok', 'details': [
            {'title': PLAN.prefix + '-' + stage, 'result': 'ok'} for stage in stages]}))
    with pytest.raises(EvidenceError):
        matched_screens(tmp_path, PLAN, observations)


@pytest.mark.parametrize('fault', ['stale-request', 'stale-reply', 'missing-result', 'changed-settings'])
def test_controller_failure_never_acknowledges_or_retries(tmp_path, fault):
    journey = InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), PLAN)
    stage = 'return-second'
    journey.steps = [{'stage': name} for name in PLAN.stages[:PLAN.stages.index(stage)]]
    settings = {'child': 'fixture-child', 'limit_enabled': False, 'allowance': ['1 hour']}
    journey.check_settings('baseline-second', {'ui': {'settings': settings}})
    observed = {'operation': 'parent-screen-page', 'outcome': 'passed', 'settings': dict(settings)}
    if fault == 'missing-result':
        del observed['settings']
    if fault == 'changed-settings':
        observed['settings']['allowance'] = ['0 minutes']
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'boot'}))
    journey.ui = SimpleNamespace(observe=Mock(return_value=observed))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({
        'stage': 'return-first' if fault == 'stale-request' else stage, 'screenshot': None}))
    reply = tmp_path / (stage + '.reply.json')
    if fault == 'stale-reply':
        reply.write_text('old')
    with pytest.raises(EvidenceError):
        journey.step(Mock())
    if fault == 'stale-reply':
        assert reply.read_text() == 'old'
    else:
        assert not reply.exists()
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.validate()
    journey.progress.assert_not_called()


def test_qualification_stores_assertion_before_advancing_and_acknowledging():
    qualification = object.__new__(RepeatedOperationsQualification)
    qualification.result = {}
    events = []
    qualification.checkpoint = lambda event: events.append((
        event, json.loads(json.dumps(qualification.result))))
    observed = {'stage': 'return-first', 'comparison': {'outcome': 'passed'},
                'assertion': {'id': 'first-return', 'phase': 'step-1'}}
    qualification.record_progress(SimpleNamespace(plan=PLAN, steps=[observed]),
                                  'return-first', observed)
    assert [event for event, _ in events] == ['stage-observed', 'assertion', 'phase-started']
    assert [state['active_phase'] for _, state in events] == ['step-1', 'step-1', 'step-2']
    assert events[1][1]['assertions'] == [{
        'stage': 'return-first', 'id': 'first-return', 'phase': 'step-1', 'outcome': 'passed'}]
