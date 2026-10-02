"""Cases 44/45 composition, single exit, preserved activity and failure stops.

Parallelism: private pytest evidence, process-local doubles and bounded waited
Perl children; no live display, VM, bus, socket, shared files or caches.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import installed_journey
from installed_journey import matched_screens
from native_fixtures import fixture_actions
from overlay_cancel import PLAN, ESCAPE_PLAN, execute, execute_escape
from private_artifacts import EvidenceError
from request_composition import KioskRequestJourney
from tests.support.perl import run_perl


@pytest.mark.parametrize('plan,callback', [(PLAN, execute), (ESCAPE_PLAN, execute_escape)],
                         ids=['cancel', 'escape'])
def test_real_case_recorder_startup_uses_shared_journey_and_verify_only(monkeypatch, tmp_path, plan, callback):
    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        guestfs=Mock(), commands=Mock(), verified=SimpleNamespace(inputs={}))
    def worker(**kwargs):
        journey = kwargs['guarded_observe'].__self__
        assert type(journey) is KioskRequestJourney and journey.plan is plan
        assert set(journey.actions) == {'native-verify'}
        journey.progress('open-estimate', {'stage': 'open-estimate'})
        assert recorder.step.call_args.args == ('step-2',)
        recorder.assertion.assert_not_called()
        journey.progress('resumed-submitted', {'stage': 'resumed-submitted'})
        assert recorder.assertion.call_args.args == ('visible-result',)
        return dict(shutdown_verified=True, worker_stopped=True,
                    callback_closed=True, outcome='passed')
    context.run_worker = worker
    monkeypatch.setattr(KioskRequestJourney, 'validate', lambda self: [])
    callback(recorder, context)
    context.credentials.provision.assert_called_once()
    assert plan.balance_checks == {'allowance-configured': 900}
    assert plan.activity_checks == {stage: ('activity-capture', 'same')
                                   for stage in ('activity-returned', 'resumed-opened')}


@pytest.mark.parametrize('include_refusal', [True, False])
def test_shared_fixture_action_selection_preserves_verification_owner(monkeypatch, include_refusal):
    import native_fixtures
    controller = Mock()
    monkeypatch.setattr(native_fixtures, 'NativeFixtures', Mock(return_value=controller))
    actions = fixture_actions(include_refusal=include_refusal)
    assert set(actions) == ({'native-refuse', 'native-verify'} if include_refusal else {'native-verify'})
    journey = SimpleNamespace(transport=object(), context=SimpleNamespace(verified=object()))
    guard = Mock()
    actions['native-verify'](journey, guard)
    controller.verify.assert_called_once()
    if include_refusal:
        actions['native-refuse'](journey, guard)
        controller.refuse.assert_called_once()
    native_fixtures.NativeFixtures.assert_called_once_with(journey.transport, journey.context.verified)
    assert guard.call_count == len(actions)
    assert set(fixture_actions()) == {'native-refuse', 'native-verify'}
    with pytest.raises(EvidenceError, match='action-binding'):
        fixture_actions(include_refusal=1)


@pytest.mark.parametrize('fault', [None, 'window', 'draft', 'missing', 'replay', 'mutated-capture'])
@pytest.mark.parametrize('stage', ['activity-returned', 'resumed-opened'])
@pytest.mark.parametrize('plan', [PLAN, ESCAPE_PLAN], ids=['cancel', 'escape'])
def test_case_activity_check_precedes_reply_and_resumed_input(tmp_path, fault, stage, plan):
    journey = KioskRequestJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
                                  actions=fixture_actions(include_refusal=False))
    value = {'binding': 'native-primary', 'pid': 123, 'endpoint': [':1.50', '/accessible/1'],
             'state': {'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft',
                       'score': 'Moves: 0; token: 0'}}
    current = deepcopy(value)
    if fault != 'missing': journey.check_activity('activity-capture', {'ui': {'activity': value}})
    if fault == 'window': current['endpoint'][1] = '/replacement'
    if fault in ('draft', 'mutated-capture'): current['state']['draft'] = 'changed'
    if fault == 'mutated-capture': value['state']['draft'] = 'changed'
    if fault == 'replay': journey.check_activity(stage, {'ui': {'activity': current}})
    journey.steps = [{'stage': earlier} for earlier in plan.stages[:plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'overlay-native-activity', 'outcome': 'passed', 'interface': 'AT-SPI',
        'activity': current}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({
        'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        assert journey.failed
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['comparison']['same_window'] is True


@pytest.mark.parametrize('plan,exit,fault', [
    (plan, exit, fault) for plan, exit in ((PLAN, 'overlay'), (ESCAPE_PLAN, 'overlay-escape'))
    for fault in ('', *plan.screen_tags)
], ids=[exit + '-' + (fault or 'success')
        for plan, exit in ((PLAN, 'overlay'), (ESCAPE_PLAN, 'overlay-escape'))
        for fault in ('', *plan.screen_tags)])
def test_actual_worker_order_titles_and_every_stage_failure_stop(tmp_path, plan, exit, fault):
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events; our $fault = shift @ARGV; our $exit = shift @ARGV;
our $declared = decode_json(shift @ARGV); our $challenges = decode_json(shift @ARGV);
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub record_info { push @main::events, ['marker', $_[0]] }
sub get_var { '1' } sub get_required_var { 'synthetic-secret' }
sub type_password { push @main::events, ['password'] }
sub send_key { push @main::events, ['key', $_[0]] }
sub type_string { push @main::events, ['text', $_[0]] }
package main; require onpc_kiosk_cancel;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_kiosk_cancel::run(sub {
        my ($stage) = @_; push @events, ['seen', $stage]; die 'refused' if $stage eq $fault;
        my $reply = {observed => $stage, ($stage =~ /(?:greeter|picker-opened)$/ ? (ui_focused => JSON::PP::true) : ())};
        for my $id (keys %$challenges) {
            my ($role, $first, $second) = @{$challenges->{$id}};
            if ($stage eq $first || $stage eq $second) {
                $reply->{challenge} = {id => $id, role => $role, surface => 'gdm',
                    check => $stage eq $first ? 'qualified' : 'rechecked'};
                push @events, ['challenge', $stage, $reply->{challenge}];
            }
        }
        return $reply;
    }, $exit, $declared, $challenges); 1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
''', fault, exit, json.dumps(plan.invocations), json.dumps(plan.challenges)).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'seen']
    expected = list(plan.screen_tags)
    assert bool(result['ok']) == (not fault), result['error']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if fault:
        assert ['finish'] not in result['events']
        if exit == 'overlay-escape' and expected.index(fault) <= expected.index('escape-ready'):
            assert ['key', 'esc'] not in result['events']
    else:
        details = [{'title': event[1], 'result': 'ok'} for event in result['events'] if event[0] == 'marker']
        proofs = {event[1]: event[2] for event in result['events'] if event[0] == 'challenge'}
        observations = [{'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
            'operation': tag.split(':', 1)[1], 'outcome': 'passed',
            'interface': 'AT-SPI' if tag.startswith('ui:') else 'system session'},
            **({'challenge': proofs[stage]} if stage in proofs else {})}
            for stage, tag in plan.screen_tags.items()]
        (tmp_path / 'testresults').mkdir()
        (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
        assert len(matched_screens(tmp_path, plan, observations)) == len(expected)
        assert stages.count('cancel') == (exit == 'overlay')
        assert stages.index('activity-returned') < stages.index('resumed-submit')
        assert sum(event[0] == 'password' for event in result['events']) == 2
        assert [event[1] for event in result['events'] if event[0] == 'text'] == ['1.25']
        assert result['events'].count(['key', 'esc']) == (exit == 'overlay-escape')
        if exit == 'overlay-escape':
            ready = result['events'].index(['seen', 'escape-ready'])
            key = result['events'].index(['key', 'esc'])
            returned = result['events'].index(['seen', 'escape-returned'])
            assert ready < key < returned
