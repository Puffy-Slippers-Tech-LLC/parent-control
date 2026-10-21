"""Finite history composition, public policy comparisons and owned reply gates.

Parallelism: pytest-private files, in-process doubles and bounded waited Perl
children only. No live VM, display, bus, service or shared mutable cache.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import accessible_ui
import baseline_app_effects as effects
import check_graphical_smoke as smoke
from installed_journey import matched_screens, record_installed_journey
from parent_setup_qualification import BaselineAppEffectsQualification, KioskEntryQualification
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.perl import run_perl
from tests.support.paths import ROOT
from ui_observations import OPERATION_LABELS


WORKER = r'''
use strict; use warnings; use JSON::PP qw(decode_json encode_json);
our @events; our $fault = shift @ARGV;
our $declared = decode_json(shift @ARGV); our $challenges = decode_json(shift @ARGV);
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['marker', $_[0]] }
sub current_console { 'sut' }
sub get_var { '1' }
sub get_required_var { 'synthetic-fixture-secret' }
sub type_password { push @main::events, ['password'] }
sub type_string { die 'unexpected-native-text' }
sub send_key { push @main::events, ['key', $_[0]] }
package main;
require onpc_baseline_app_effects;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub {};
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval { onpc_baseline_app_effects::run(sub {
    my ($stage) = @_; push @events, ['seen', $stage];
    die 'refused' if $stage eq $fault;
    my $reply = {observed => $stage, ($stage =~ /(?:greeter|list)$/ ? (ui_focused => JSON::PP::true) : ())};
    $reply->{station_destination} = 'default-request-form' if $stage eq 'cancel-station-branch';
    for my $id (keys %$challenges) {
        my ($role, $first, $second) = @{$challenges->{$id}};
        $reply->{challenge} = {id => $id, role => $role, surface => 'gdm',
            check => $stage eq $first ? 'qualified' : 'rechecked'}
            if $stage eq $first || $stage eq $second;
    }
    return $reply;
}, $declared, $challenges); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''


@pytest.mark.parametrize('fault', ['', *effects.PLAN.screen_tags])
def test_real_worker_order_and_each_refusal_stops(fault, tmp_path):
    result = json.loads(run_perl(WORKER, fault, json.dumps(effects.PLAN.invocations),
                                 json.dumps(effects.PLAN.challenges)).stdout)
    stages = list(effects.PLAN.screen_tags)
    assert bool(result['ok']) == (not fault), result['error']
    assert [item[1] for item in result['events'] if item[0] == 'seen'] == (
        stages[:stages.index(fault) + 1] if fault else stages)
    if fault:
        assert ['finish'] not in result['events']
    else:
        assert sum(item[0] == 'password' for item in result['events']) == 5
        details = [{'title': item[1], 'result': 'ok'} for item in result['events'] if item[0] == 'marker']
        observations = []
        for stage, tag in effects.PLAN.screen_tags.items():
            value = {'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
                'operation': tag.split(':', 1)[1], 'outcome': 'passed'}}
            challenge = effects.PLAN.challenge_at(stage)
            if challenge:
                value['challenge'] = challenge
            observations.append(value)
        directory = tmp_path / 'testresults'
        directory.mkdir()
        (directory / 'result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
        assert [item['stage'] for item in matched_screens(tmp_path, effects.PLAN, observations)] == stages


def policy(grant=0, timestamp=1_000_000_000):
    return {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
        'apps': [[effects.MATCH_APPS[role], access, 'pattern' if role == 'S' else 'precise']
                 for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))],
        'rules': [[effects.MATCH_APPS[role], effects.RULES[role]] for role in ('A', 'H', 'S')],
        'balances': {'child': 'fixture-child', 'observed_monotonic_ns': timestamp,
            **{key: {'seconds': seconds, 'precision_seconds': 60}
               for key, seconds in (('daily', 0), ('one_time', grant), ('total', grant))}},
        'read_bounds': [timestamp, timestamp + 1]}


def journey(tmp_path):
    return effects.BaselineAppEffectsJourney(SimpleNamespace(directory=tmp_path), Mock())


@pytest.mark.parametrize('fault', [None, 'settings', 'hard-access', 'soft-rule', 'missing-app',
    'daily', 'total', 'wrong-child', 'missing-estimate', 'elapsed', 'too-large', 'zero-grant',
    'changed-other-policy', 'missing-capture', 'replay'])
def test_independent_grant_policy_read_refuses_bad_evidence_before_durable_reply(tmp_path, fault):
    active = journey(tmp_path)
    original = policy()
    active.check_settings('saved-policy', {'ui': {'revoke_cancel': original}})
    original['rules'][0][1] = 'mutated-decoder-record'
    active.effects_estimate = {'estimate': {'kind': 'fixed', 'seconds': 600},
                               'observed_monotonic_ns': 1_000_000_000}
    value = policy(540, 61_000_000_000)
    if fault == 'settings': value['settings']['limit_enabled'] = False
    if fault == 'hard-access': value['apps'][1][1] = 'allowed'
    if fault == 'soft-rule': value['rules'][2][1] = effects.RULES['A']
    if fault == 'missing-app': value['apps'].pop()
    if fault == 'daily': value['balances']['daily']['seconds'] = 1
    if fault == 'total': value['balances']['total']['seconds'] += 1
    if fault == 'wrong-child': value['balances']['child'] = 'existing-fixture-child'
    if fault == 'missing-estimate': active.effects_estimate = None
    if fault == 'elapsed': value['balances']['observed_monotonic_ns'] = 602_000_000_000
    if fault == 'too-large': value['balances']['one_time']['seconds'] = value['balances']['total']['seconds'] = 700
    if fault == 'zero-grant': value['balances']['one_time']['seconds'] = value['balances']['total']['seconds'] = 0
    if fault == 'changed-other-policy': value['rules'].append(['unrelated-row', 'changed'])
    if fault == 'missing-capture': active.effects_seen.clear()
    if fault == 'replay': active.effects_seen['granted-policy'] = policy()
    stage = 'granted-policy'
    active.steps = [{'stage': prior} for prior in effects.PLAN.stages[:effects.PLAN.stages.index(stage)]]
    active.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': effects.PLAN.screen_tags[stage][3:], 'revoke_cancel': value}))
    active.boot = 'b' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError):
            active.step(Mock())
        assert active.failed and not (tmp_path / (stage + '.reply.json')).exists()
        active.progress.assert_not_called()
    else:
        active.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert active.steps[-1]['comparison']['positive_grant_with_elapsed_bounds']


@pytest.mark.parametrize('grant', [0, 1])
def test_confirmed_revocation_requires_exact_zero_and_unchanged_saved_rules(tmp_path, grant):
    active = journey(tmp_path)
    active.check_settings('saved-policy', {'ui': {'revoke_cancel': policy()}})
    if grant:
        with pytest.raises(EvidenceError, match='grant-only-balance'):
            active.check_settings('revoked-policy', {'ui': {'revoke_cancel': policy(grant)}})
    else:
        result = {'ui': {'revoke_cancel': policy()}}
        active.check_settings('revoked-policy', result)
        assert result['comparison']['zero_grant'] and result['comparison']['unchanged_saved_policy']


def test_real_recorder_constructor_owns_fixture_actions_and_finite_worker(tmp_path):
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    context.recorder = recorder = MagicMock(assertion=Mock())
    def worker(**options):
        active = options['guarded_observe'].__self__
        assert type(active) is effects.BaselineAppEffectsJourney and active.plan is effects.PLAN
        assert set(active.actions) == {'native-refuse', 'native-verify'}
        assert options['authenticate'] is True and options['timeout'] == 1800
        raise EvidenceError('synthetic-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-stop'):
        record_installed_journey(recorder, context, effects.PLAN,
            actions=effects.fixture_actions(), journey_type=effects.BaselineAppEffectsJourney, timeout=1800)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


def test_registration_and_required_public_operations():
    assert issubclass(BaselineAppEffectsQualification, KioskEntryQualification)
    for stage, tag in effects.PLAN.screen_tags.items():
        if tag.startswith('ui:'):
            assert tag[3:] in accessible_ui.OPERATIONS and tag[3:] in OPERATION_LABELS, stage


@pytest.mark.parametrize('fault', ['', 'setup-detached'])
def test_real_dispatch_preloads_helper_before_loader_search_path_is_removed(fault):
    source = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    program = r'''
use strict; use warnings; use JSON::PP;
our $fault = shift @ARGV; our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'basetest.pm'} = 1; }
package basetest; sub new { bless {}, shift }
package testapi;
sub import { no strict 'refs'; *{caller() . '::console'} = \&console;
    *{caller() . '::select_console'} = \&select_console; }
sub console { push @main::events, ['console', $_[0]]; bless {}, 'Console' }
sub select_console { die 'unexpected-console-input' }
package Console; sub disable { push @main::events, ['disabled'] }
package main;
my $source = decode_json(SOURCE_JSON);
while ($source =~ /use (onpc_\w+)/g) { $INC{"$1.pm"} = 1; }
eval 'package DispatchProbe;' . $source; die $@ if $@;
{
    no warnings 'redefine';
    *DispatchProbe::exchange = sub {
        push @events, ['stage', $_[0]]; die 'refused' if $_[0] eq $fault;
        return {baseline_app_effects => JSON::PP::true, invocations => ['finite'],
            challenge_bindings => {login => ['child', 'one', 'two']}};
    };
    *onpc_baseline_app_effects::run = sub {
        die 'worker:callback' unless ref($_[0]) eq 'CODE';
        push @events, ['worker', $_[1], $_[2]];
    };
}
my $ok = eval { local @INC = (); DispatchProbe::run(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => "$@", events => \@events});
'''
    literal = "'" + json.dumps(source).replace('\\', '\\\\').replace("'", "\\'") + "'"
    result = json.loads(run_perl(program.replace('SOURCE_JSON', literal), fault).stdout)
    expected = [['stage', 'ready'], ['console', 'sut'], ['disabled'], ['stage', 'setup-detached']]
    if not fault:
        expected.append(['worker', ['finite'], {'login': ['child', 'one', 'two']}])
    assert bool(result['ok']) == (not fault), result['error']
    assert result['events'] == expected


@pytest.mark.parametrize('kwargs', [dict(baseline_app_effects=True),
    dict(baseline_app_effects=True, assets='synthetic', provision_credentials=True, kiosk_entry=True)])
def test_dispatcher_refuses_invalid_selection_before_resource_discovery(kwargs):
    with pytest.raises(CommandError, match='baseline-app-effects-prerequisites'):
        smoke.main(**kwargs)
