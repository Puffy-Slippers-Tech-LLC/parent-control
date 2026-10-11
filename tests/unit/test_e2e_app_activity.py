"""APP04/FLOW08 public identity, immutable captures and real worker gates.

Parallelism: private pytest evidence, process-local public UI/transport doubles
and bounded waited Perl children. No live VM, display, bus or shared cache.
"""
from dataclasses import FrozenInstanceError, replace
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import accessible_ui
from accessible_ui import UiError
import check_e2e_app_activity as check
import check_graphical_smoke as smoke
from installed_journey import (InstalledJourney, JourneyPlan, matched_screens,
                               record_installed_journey)
from journey_blocks import native_usable_app
from native_activity import PLAN, NativeActivityJourney
from app_launch import PLAN as CASE_PLAN, DISABLED_PLAN
from policy_edits import AppPolicyJourney
from native_fixtures import fixture_actions
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, NativeActivityQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from ui_observations import (AppActivityObservation, OPERATION_LABELS, UiObservations,
                             compare_app_activity)


def activity(bus=':1.50', path='/org/a11y/atspi/accessible/1', pid=123):
    return {'binding': 'native-primary', 'pid': pid, 'endpoint': [bus, path],
            'state': {'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft',
                      'score': 'Moves: 0; token: 0'}}


@pytest.mark.parametrize('field', ['binding', 'pid', 'endpoint', 'state'])
def test_immutable_capture_and_each_comparison_field(field):
    original = activity()
    captured = AppActivityObservation.from_value(original)
    original['endpoint'][1] = '/replacement'
    original['state']['draft'] = 'changed'
    assert captured == AppActivityObservation.from_value(activity())
    with pytest.raises(FrozenInstanceError):
        captured.pid = 999
    values = {'binding': 'other', 'pid': 999, 'endpoint': (':1.50', '/replacement'),
              'state': ('changed', *captured.state[1:])}
    changed = replace(captured, **{field: values[field]})
    with pytest.raises(EvidenceError):
        compare_app_activity(changed, captured)
    if field != 'state':
        assert compare_app_activity(changed, captured, result='replaced')['same_window'] is False
    assert compare_app_activity(captured, captured)['same_window'] is True
    with pytest.raises(EvidenceError):
        compare_app_activity(captured, captured, result='replaced')


@pytest.mark.parametrize('fault', [None, 'missing', 'extra', 'pid', 'bus', 'path', 'text', 'state-extra'])
def test_real_controller_decoder_validates_complete_public_activity(fault):
    value = activity()
    if fault == 'missing': del value['state']
    if fault == 'extra': value['private'] = 'canary'
    if fault == 'pid': value['pid'] = True
    if fault == 'bus': value['endpoint'][0] = 'not-a-bus'
    if fault == 'path': value['endpoint'][1] = 'not-a-path'
    if fault == 'text': value['state']['submitted'] = 'No submitted draft'
    if fault == 'state-extra': value['state']['private'] = 'canary'
    reply = {'operation': 'native-activity', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
             'activity': value, 'boot_sha256': 'b' * 64}
    observer = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(reply).encode())))
    observer.boot_guard = ''
    if fault:
        with pytest.raises(EvidenceError): observer.observe('native-activity')
    else:
        assert observer.observe('native-activity')['activity'] == value


@pytest.mark.parametrize('fault', [None, 'inactive', 'owner', 'absent', 'endpoint', 'text'])
def test_public_read_resolves_owned_window_and_never_inputs(fault):
    scope = 'onpc-fixture-native-primary'
    nodes = {name: Node(text, 'label', identity=scope + '-' + name)
             for name, text in {'status': 'Ready', 'draft': 'ONPC fixture draft',
                 'submitted': 'ONPC fixture draft', 'score': 'Moves: 0; token: 0'}.items()}
    nodes['draft'].get_text_iface = lambda: nodes['draft']
    surface = Node(identity=scope, children=nodes.values())
    surface.states.add('active')
    surface.bus, surface.path = ':1.50', '/org/a11y/atspi/accessible/1'
    surface.get_process_id = lambda: 123
    owner = Node(role='application', identity='com.puffyslippers.ONPCFixture.native.primary',
                 children=[surface])
    root = Node(role='desktop', children=[owner])
    ui = ui_for(Node())
    ui.api.get_desktop = lambda _: root
    ui.api.Text = SimpleNamespace(get_character_count=lambda n: len(n.name),
                                 get_text=lambda n, a, b: n.name[a:b])
    ui.activate_id = Mock()
    if fault == 'inactive': surface.states.remove('active')
    if fault == 'owner': owner.identity = 'foreign'
    if fault == 'absent': owner.children.clear()
    if fault == 'endpoint': surface.bus = None
    if fault == 'text': nodes['submitted'].name = 'No submitted draft'
    if fault:
        with pytest.raises(UiError): ui.run('native-activity', '')
    else:
        assert ui.run('native-activity', '')['activity'] == activity()
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'window', 'text', 'missing', 'replay'])
def test_real_step_compares_renamed_endpoints_before_reply(tmp_path, fault):
    plan = JourneyPlan('independent', 'independent', {
        'before': 'ui:native-activity', 'after': 'ui:native-activity'}, {},
        activity_checks={'after': ('before', 'same')})
    journey = InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    value = activity()
    if fault != 'missing': journey.check_activity('before', {'ui': {'activity': value}})
    value['endpoint'][1] = '/mutated-decoder-result'
    value['state'].clear()
    current = activity(path='/replacement') if fault == 'window' else activity()
    if fault == 'text': current['state']['draft'] = 'changed'
    if fault == 'replay': journey.check_activity('after', {'ui': {'activity': current}})
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index('after')]]
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': 'native-activity', 'activity': current}))
    journey.boot = 'b' * 64
    (tmp_path / 'after.request.json').write_text(json.dumps({'stage': 'after', 'screenshot': None}))
    inherited = Mock(wraps=journey.check_settings)
    comparison = Mock(wraps=journey.check_activity)
    journey.check_settings, journey.check_activity = inherited, comparison
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / 'after.reply.json').exists()
        assert journey.failed
        journey.progress.assert_not_called()
    else:
        journey.step(Mock())
        assert (tmp_path / 'after.reply.json').exists()
        assert journey.steps[-1]['comparison'] == {
            'same_window': True, 'activity_unchanged': True, 'outcome': 'passed'}
        journey.progress.assert_called_once()
    inherited.assert_called_once()
    comparison.assert_called_once()


@pytest.mark.parametrize('binding', [('after', 'same'), ('before', 'unknown'), ('missing', 'same')])
def test_invalid_comparison_plan_refuses(binding):
    with pytest.raises(EvidenceError, match='activity-plan'):
        JourneyPlan('invalid', 'invalid', {'before': 'ui:native-activity',
                    'after': 'ui:native-activity'}, {}, activity_checks={'after': binding})


def test_registration_and_real_recorder_startup(tmp_path, monkeypatch):
    assert issubclass(NativeActivityQualification, KioskEntryQualification)
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    assert isinstance(NativeActivityQualification.journey(context, Mock()), NativeActivityJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assets = object()
    monkeypatch.setattr(check, 'named_input', Mock(return_value=assets))
    monkeypatch.setattr(check, 'smoke', Mock(return_value=0))
    assert check.main() == 0
    check.smoke.assert_called_once_with(assets=assets, provision_credentials=True, app_activity=True)
    for changes in ({}, {'assets': assets, 'provision_credentials': True, 'native_app': True}):
        with pytest.raises(CommandError, match='app-activity-prerequisites'):
            smoke.main(app_activity=True, **changes)
    assert {tag[3:] for tag in PLAN.screen_tags.values() if tag.startswith('ui:')} <= accessible_ui.OPERATIONS
    assert accessible_ui.NATIVE_APP_OPERATIONS <= OPERATION_LABELS.keys()
    recorder = MagicMock(assertion=Mock())
    context.recorder = recorder
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is NativeActivityJourney and journey.plan is PLAN
        assert set(journey.actions) == {'native-refuse', 'native-verify'}
        assert options['validate'].__self__ is journey and options['authenticate'] is True
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(recorder, context, PLAN, journey_type=NativeActivityJourney)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


WORKER = r'''
use strict; use warnings; use JSON::PP;
our @events; our $fault = shift @ARGV;
our $declared = decode_json(shift @ARGV); our $challenges = decode_json(shift @ARGV);
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['marker', $_[0]] }
sub current_console { 'sut' }
sub get_var { '1' }
sub get_required_var { 'synthetic-fixture-secret' }
sub type_password { push @main::events, ['password'] }
sub type_string { push @main::events, ['query', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
package main;
require onpc_app_rows;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub {};
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval { onpc_app_rows::app_activity(sub {
    my ($stage) = @_; push @events, ['seen', $stage];
    die 'refused' if $stage eq $fault;
    my $reply = {observed => $stage, ($stage =~ /greeter$/ ? (ui_focused => JSON::PP::true) : ())};
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


@pytest.mark.parametrize('fault', ['', *PLAN.screen_tags])
def test_actual_worker_order_markers_and_every_failure_stops(fault, tmp_path):
    result = json.loads(run_perl(WORKER, fault, json.dumps(PLAN.invocations),
                                 json.dumps(PLAN.challenges)).stdout)
    events = result['events']
    stages = list(PLAN.screen_tags)
    assert bool(result['ok']) == (not fault), result['error']
    assert [e[1] for e in events if e[0] == 'seen'] == (
        stages[:stages.index(fault) + 1] if fault else stages)
    if fault:
        assert ['finish'] not in events
    else:
        assert sum(e[0] == 'password' for e in events) == 2
        assert [e[1] for e in events if e[0] == 'query'] == ['ONPC Allowed Fixture']
        assert events[-1] == ['finish']
        details = [{'title': e[1], 'result': 'ok'} for e in events if e[0] == 'marker']
        observations = []
        for stage, tag in PLAN.screen_tags.items():
            item = {'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
                'operation': tag.split(':', 1)[1], 'outcome': 'passed',
                'interface': 'ApplicationUI+external-provider' if tag.startswith('ui:') else 'system session'}}
            challenge = PLAN.challenge_at(stage)
            if challenge: item['challenge'] = challenge
            observations.append(item)
        directory = tmp_path / 'testresults'
        directory.mkdir()
        (directory / 'result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
        assert [s['stage'] for s in matched_screens(tmp_path, PLAN, observations)] == stages


@pytest.mark.parametrize('route', ['command', 'grid'])
def test_flow_declaration_is_independently_reusable(route):
    screens = native_usable_app(route)
    screens.clear()
    stages = native_usable_app(route)
    assert stages['opened'] == 'ui:native-opened'
    assert stages['submitted'] == 'ui:native-submitted'
    assert list(stages)[-3:] == ['opened', 'submit', 'submitted']
    with pytest.raises(EvidenceError): native_usable_app('denied')
    # A renamed independent consumer uses the actual shared composition, not
    # the qualification's login/cleanup lifecycle or stage spelling.
    program = r'''
use strict; use warnings; use JSON::PP;
our @events; my $route = shift @ARGV;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi;
sub record_info {} sub send_key {push @main::events,['key',$_[0]]}
sub type_string {push @main::events,['query',$_[0]]}
package main;
require onpc_app_rows;
my $j=onpc_journey->new(exchange=>sub {push @events,['seen',$_[0]]; return {observed=>$_[0]};},
    prefix=>'independent-renamed',review=>0);
onpc_app_rows::native_usable_app($j,$route,$j->seen('desktop'));
onpc_app_rows::native_read_activity($j,'renamed-capture');
onpc_app_rows::native_read_activity($j,'renamed-compare');
print encode_json(\@events);
'''
    events = json.loads(run_perl(program, route).stdout)
    assert [e[1] for e in events if e[0] == 'seen'] == [*stages, 'renamed-capture', 'renamed-compare']


CASE_WORKER = WORKER.replace('require onpc_app_rows;', 'require onpc_app_launch;').replace(
    'onpc_app_rows::app_activity', 'onpc_app_launch::run').replace(
        '}, $declared, $challenges);', '}, $declared, $challenges, shift @ARGV);')


def test_allowed_command_worker_invalid_control_refuses_before_entry():
    result = json.loads(run_perl(CASE_WORKER, '', json.dumps(CASE_PLAN.invocations),
                                 json.dumps(CASE_PLAN.challenges), 'invalid').stdout)
    assert not result['ok'] and 'app-launch:arguments' in result['error']
    assert result['events'] == []


@pytest.mark.parametrize('plan,control,fault', [
    (plan, control, fault) for plan, control in
    ((CASE_PLAN, 'enabled'), (DISABLED_PLAN, 'disabled'))
    for fault in ('', *plan.screen_tags)])
def test_allowed_command_case_worker_order_and_every_refusal_stops(plan, control, fault, tmp_path):
    result = json.loads(run_perl(CASE_WORKER, fault, json.dumps(CASE_PLAN.invocations),
                                 json.dumps(CASE_PLAN.challenges), control).stdout)
    stages = list(plan.screen_tags)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    assert [event[1] for event in events if event[0] == 'seen'] == (
        stages[:stages.index(fault) + 1] if fault else stages)
    if fault:
        assert ['finish'] not in events
    else:
        assert sum(event[0] == 'password' for event in events) == 3
        assert not any(event[0] == 'query' for event in events)
        assert events[-1] == ['finish']
        details = [{'title': event[1], 'result': 'ok'} for event in events if event[0] == 'marker']
        observations = []
        for stage, tag in plan.screen_tags.items():
            item = {'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
                'operation': tag.split(':', 1)[1], 'outcome': 'passed',
                'interface': 'ApplicationUI+external-provider' if tag.startswith('ui:') else 'system session'}}
            challenge = plan.challenge_at(stage)
            if challenge:
                item['challenge'] = challenge
            observations.append(item)
        directory = tmp_path / 'testresults'
        directory.mkdir()
        (directory / 'result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
        assert [screen['stage'] for screen in matched_screens(tmp_path, plan, observations)] == stages


@pytest.mark.parametrize('plan', [CASE_PLAN, DISABLED_PLAN])
def test_allowed_case_declares_both_accounts_same_command_and_registered_sessions(plan):
    import session_control
    assert plan.access_checks == {'allowed-access': 'allowed'}
    if plan is CASE_PLAN:
        assert plan.balance_checks == {'allowance-configured': 1800}
        assert plan.child_bindings['allowance-configured'] == 'existing'
    else:
        assert plan.balance_checks == {}
        assert plan.settings_checks['parent-selected'].limit_enabled is False
        assert not {'allowance-configured', 'saved-settings'} & plan.screen_tags.keys()
    assert plan.screen_tags['jordan-use-command'] == 'ui:native-command-launch'
    assert plan.screen_tags['riley-use-command'] == 'ui:overlay-native-command-launch'
    assert plan.screen_tags['riley-use-submitted'] == 'ui:overlay-native-submitted'
    assert {tag[7:] for tag in plan.screen_tags.values() if tag.startswith('system:')} <= session_control.BINDINGS.keys()
    assert not any('approval' in tag or 'blocked' in tag for tag in plan.screen_tags.values())


@pytest.mark.parametrize('control', ['enabled', 'disabled'])
def test_allowed_case_uses_real_recorder_constructor_and_owned_worker(tmp_path, control):
    from app_launch import E2E_CASES
    execute = E2E_CASES['native-command-allowed-' + control]
    plan = CASE_PLAN if control == 'enabled' else DISABLED_PLAN
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    recorder = MagicMock(assertion=Mock())
    context.recorder = recorder
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is AppPolicyJourney and journey.plan is plan
        assert set(journey.actions) == {'native-verify'}
        assert options['validate'].__self__ is journey
        assert options['authenticate'] is True and options['timeout'] == 1800
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        execute(recorder, context)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()
    assert {tag[3:] for tag in plan.screen_tags.values() if tag.startswith('ui:')} <= accessible_ui.OPERATIONS


@pytest.mark.parametrize('fault', [None, 'enabled', 'allowance', 'child'])
def test_disabled_case_real_step_requires_disabled_selected_child_before_reply(tmp_path, fault):
    stage = 'parent-selected'
    settings = {'child': 'existing-fixture-child', 'limit_enabled': False,
                'allowance': ['0 minutes']}
    if fault == 'enabled': settings['limit_enabled'] = True
    if fault == 'allowance': settings['allowance'] = ['30 minutes']
    if fault == 'child': settings['child'] = 'fixture-child'
    journey = AppPolicyJourney(SimpleNamespace(directory=tmp_path), Mock(), DISABLED_PLAN,
                              actions=fixture_actions(include_refusal=False))
    journey.steps = [{'stage': earlier} for earlier in
                     DISABLED_PLAN.stages[:DISABLED_PLAN.stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': DISABLED_PLAN.screen_tags[stage][3:], 'settings': settings}))
    journey.boot = 'b' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert journey.failed and not (tmp_path / (stage + '.reply.json')).exists()
        journey.progress.assert_not_called()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['comparison']
        journey.progress.assert_called_once()


@pytest.mark.parametrize('stage', ['allowance-configured', 'allowed-access', 'allowed-match'])
@pytest.mark.parametrize('fault', [False, True])
def test_allowed_case_real_step_checks_policy_and_balances_before_reply(tmp_path, stage, fault):
    from accessible_ui import MATCH_APP, MATCH_RULES
    ui_value = ({'time_explanation': {
        key: {'seconds': seconds, 'precision_seconds': 60} for key, seconds in
        zip(('daily', 'one_time', 'total'), (0 if fault else 1800, 0, 1800))}}
        if stage == 'allowance-configured' else
        {'access': {'app': MATCH_APP, 'choice': 'conditional' if fault else 'allowed'}}
        if stage == 'allowed-access' else
        {'match': {'app': MATCH_APP, 'rule': MATCH_RULES[1] if fault else MATCH_RULES[0]}})
    if stage == 'allowance-configured':
        ui_value['time_explanation']['observed_monotonic_ns'] = 1
    journey = AppPolicyJourney(SimpleNamespace(directory=tmp_path), Mock(), CASE_PLAN,
                              actions=fixture_actions(include_refusal=False))
    journey.steps = [{'stage': earlier} for earlier in CASE_PLAN.stages[:CASE_PLAN.stages.index(stage)]]
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': CASE_PLAN.screen_tags[stage][3:], **ui_value}))
    journey.boot = 'b' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError):
            journey.step(Mock())
        assert journey.failed
        assert not (tmp_path / (stage + '.reply.json')).exists()
        journey.progress.assert_not_called()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['comparison']
        journey.progress.assert_called_once()
