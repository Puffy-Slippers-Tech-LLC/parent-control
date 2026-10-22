"""Private records, UI doubles and bounded waited Perl children; no live owner."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import accessible_ui as ui
import baseline_journey as baseline
from installed_journey import JourneyPlan, matched_screens, record_installed_journey
from private_artifacts import EvidenceError
from request_composition import GrantAppEffectsJourney
from request_flow import continued_request
from journey_blocks import native_activity_entry, native_usable_app, retained_parent_entry
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import accounts_form
from tests.support.e2e_composition import CASE_MODULES, composition_errors
from tests.support.paths import ROOT
from tests.support.perl import run_perl
from ui_observations import OPERATION_LABELS, RequestObservation, UiObservations


WORKER = r'''
use strict; use warnings; use JSON::PP qw(decode_json encode_json);
our @events; our ($fault,$plan) = @ARGV; $plan=decode_json($plan);
BEGIN { $INC{'testapi.pm'}=1; }
package testapi;
sub record_info { push @main::events, ['marker',$_[0]] }
sub current_console { 'sut' } sub get_var { '1' }
sub get_required_var { 'synthetic-private-fixture-secret' }
sub type_password { push @main::events,['password'] }
sub type_string { die 'unexpected-native-text' }
sub send_key { push @main::events,['key',$_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events,['power',$_[0]] }
sub check_shutdown { 1 }
package Console; sub disable {}
package main;
require onpc_baseline_journey;
no warnings 'redefine'; *onpc_gdm::reattach_functional = sub {};
my $ok=eval { onpc_baseline_journey::run(sub {
    my ($stage,$image,$input)=@_; push @events,['seen',$stage];
    die 'refused' if $fault eq $stage;
    my $reply={observed=>$stage};
    $reply->{ui_focused}=JSON::PP::true if $stage =~ /(?:greeter|list)$/;
    $reply->{station_destination}='default-request-form' if $stage =~ /station-branch$/;
    $reply->{gdm_return_state}='account-list' if $stage eq 'zero-child-denied-return-state';
    for my $id (keys %{$plan->{challenges}}) {
        my ($role,$first,$second)=@{$plan->{challenges}{$id}};
        $reply->{challenge}={id=>$id,role=>$role,surface=>'gdm',
            check=>$stage eq $first ? 'qualified':'rechecked'} if $stage eq $first || $stage eq $second;
    }
    if ($input) {
        my $source='a' x 64;
        $input->({stage=>$stage,binding=>'overlay-approve',child=>'child',
            source=>$source,token=>substr($source,0,32),values=>['ret']});
    }
    return $reply;
},$plan->{invocations},$plan->{challenges});1;};
print encode_json({ok=>$ok?1:0,error=>"$@",events=>\@events});
'''


@pytest.mark.parametrize('fault', ['', *baseline.PLAN.screen_tags])
def test_actual_complete_worker_order_titles_and_each_refusal(tmp_path, fault):
    result = json.loads(run_perl(WORKER, fault, json.dumps({
        'invocations': baseline.PLAN.invocations, 'challenges': baseline.PLAN.challenges})).stdout)
    stages = list(baseline.PLAN.screen_tags)
    assert bool(result['ok']) == (not fault), result['error']
    assert [item[1] for item in result['events'] if item[0] == 'seen'] == (
        stages[:stages.index(fault) + 1] if fault else stages)
    if fault:
        boundary = result['events'].index(['seen', fault])
        assert not any(item[0] in ('password', 'key', 'power') for item in result['events'][boundary + 1:])
    else:
        assert ['power', 'off'] in result['events']
        observations = []
        for stage, tag in baseline.PLAN.screen_tags.items():
            value = {'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
                'operation': tag.split(':', 1)[1], 'outcome': 'passed'}}
            if baseline.PLAN.challenge_at(stage):
                value['challenge'] = baseline.PLAN.challenge_at(stage)
            observations.append(value)
        results = tmp_path / 'testresults'
        results.mkdir()
        (results / 'result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': [
            {'title': item[1], 'result': 'ok'} for item in result['events'] if item[0] == 'marker']}))
        assert [item['stage'] for item in matched_screens(tmp_path, baseline.PLAN, observations)] == stages


def test_composition_preflight_and_all_real_registries():
    import session_control
    source = (ROOT / 'tests/e2e/baseline_journey.py').read_text()
    assert composition_errors(source, CASE_MODULES) == []
    for tag in baseline.PLAN.screen_tags.values():
        if tag.startswith('ui:'):
            assert tag[3:] in ui.OPERATIONS and tag[3:] in OPERATION_LABELS
        elif tag.startswith('system:'):
            assert tag[7:] in session_control.BINDINGS
    assert baseline.TIMEOUT == 1800
    assert list(baseline.PLAN.screen_tags).index('rejection-policy') < list(
        baseline.PLAN.screen_tags).index('kiosk-cancel-flow-cancel')
    assert list(baseline.PLAN.screen_tags).index('cancel-policy') < list(
        baseline.PLAN.screen_tags).index('kiosk-first-approval-open')


def test_guarded_entry_omits_only_duplicate_desktop_reads_and_keeps_defaults():
    for helper, args, options in (
        (native_usable_app, ('command',), {}),
        (native_activity_entry, ('renamed',), {}),
        (retained_parent_entry, (), {'source': 'same-user'}),
    ):
        original = helper(*args, **options)
        compact = helper(*args, **options, desktop_observation=False)
        desktop = 'renamed-desktop' if helper is native_activity_entry else 'desktop'
        assert compact == {key: value for key, value in original.items() if key != desktop}
        assert helper(*args, **options) == original
    for helper, args, options in (
        (native_usable_app, ('grid',), {}),
        (native_activity_entry, ('renamed',), {'route': 'grid'}),
        (retained_parent_entry, (), {'source': 'desktop'}),
        (retained_parent_entry, (), {'source': 'child-desktop'}),
    ):
        with pytest.raises(EvidenceError): helper(*args, **options, desktop_observation=False)
    for invalid in (None, 0, 1, 'false'):
        with pytest.raises(EvidenceError): native_usable_app('command', desktop_observation=invalid)
        with pytest.raises(EvidenceError): retained_parent_entry(source='same-user', desktop_observation=invalid)


GUARDED_ENTRY_WORKER = r'''
use strict; use warnings; use JSON::PP;
our @events; my ($mode,$fault)=@ARGV;
BEGIN {$INC{'testapi.pm'}=1;}
package testapi; sub record_info {} sub send_key {die 'unexpected-key'}
package main;
require onpc_app_rows;
my $j=onpc_journey->new(exchange=>sub {
    push @events,$_[0]; die 'refused' if $_[0] eq $fault;
    return {observed=>$_[0]};
},prefix=>'renamed',review=>0);
my $ok=eval {
    if ($mode eq 'native') {onpc_app_rows::native_usable_app($j,'command',undef,'child','S');}
    elsif ($mode eq 'activity') {onpc_app_rows::native_activity_entry($j,'independent','command','child',0);}
    elsif ($mode eq 'parent') {onpc_parent::open_for_child($j,'desktop','same-user','retained','child','independent',0);}
    elsif ($mode eq 'grid') {onpc_app_rows::native_usable_app($j,'grid',undef,'child');}
    elsif ($mode eq 'grid-activity') {onpc_app_rows::native_activity_entry($j,'independent','grid','child',0);}
    elsif ($mode eq 'retained-entry') {onpc_parent::open_for_child($j,'desktop','retained','retained','child','independent',0);}
    elsif ($mode eq 'new-window') {onpc_parent::open_for_child($j,'desktop','same-user','new','child','independent',0);}
    elsif ($mode eq 'bad-parent-flag') {onpc_parent::open_for_child($j,'desktop','same-user','retained','child','independent',undef);}
    elsif ($mode eq 'bad-activity-flag') {onpc_app_rows::native_activity_entry($j,'independent','command','child',undef);}
    elsif ($mode eq 'stale-native') {
        my $old=$j->seen('desktop'); $j->seen('later');
        onpc_app_rows::native_usable_app($j,'command',$old,'child','S');
    }
    1;
};
print encode_json({ok=>$ok?1:0,error=>"$@",events=>\@events});
'''


@pytest.mark.parametrize('mode,stages', [
    ('native', ['command', 'opened', 'submit', 'submitted']),
    ('activity', ['independent-' + stage for stage in ('command', 'opened', 'submit', 'submitted', 'capture')]),
    ('parent', ['independent-parent-retained']),
])
def test_independent_guarded_worker_entry_preserves_each_result_and_refusal(mode, stages):
    for fault in ('', *stages):
        result = json.loads(run_perl(GUARDED_ENTRY_WORKER, mode, fault).stdout)
        assert bool(result['ok']) == (not fault), result['error']
        assert result['events'] == (stages[:stages.index(fault) + 1] if fault else stages)


@pytest.mark.parametrize('mode', ['grid', 'grid-activity', 'retained-entry', 'new-window',
                                'bad-parent-flag', 'bad-activity-flag', 'stale-native'])
def test_guarded_worker_rejects_unsupported_or_stale_entry_before_launch(mode):
    result = json.loads(run_perl(GUARDED_ENTRY_WORKER, mode, '').stdout)
    assert not result['ok'] and result['error']
    assert result['events'] == (['desktop', 'later'] if mode == 'stale-native' else [])


def request(*, seconds=75, overlay=True):
    return dict(surface='child-overlay' if overlay else 'kiosk', form_count=1,
        child='fixture-child', approver='fixture-parent', duration_seconds=seconds,
        custom_text='1.25' if seconds == 75 else '10', allow_soft=True,
        child_selector_enabled=not overlay, approver_selector_enabled=True,
        duration_enabled=True, soft_choice_enabled=True, request_enabled=True,
        cancel_enabled=True, message='', mute=None)


def choice(*, seconds=75, estimate=675, timestamp=1, overlay=True):
    return {'request': request(seconds=seconds, overlay=overlay),
            'estimate': {'kind': 'fixed', **ui.duration_projection(
                f'{estimate // 60}m {estimate % 60}s')},
            'observed_monotonic_ns': timestamp * 1_000_000_000}


def policy(grant=0, timestamp=1):
    return {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
        'apps': [[baseline.MATCH_APPS[role], access, 'pattern' if role == 'S' else 'precise']
                 for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))],
        'rules': [[baseline.MATCH_APPS[role], baseline.RULES[role]] for role in ('A', 'H', 'S')],
        'balances': {'child': 'fixture-child', 'observed_monotonic_ns': timestamp * 1_000_000_000,
            **{key: {'seconds': seconds, 'precision_seconds': 1}
               for key, seconds in (('daily', 0), ('one_time', grant), ('total', grant))}},
        'read_bounds': [timestamp * 1_000_000_000, timestamp * 1_000_000_000 + 1]}


def effects(tmp_path, *, negative=False):
    plan = JourneyPlan('independent', 'independent', {
        'baseline': 'ui:revoke-saved-balances',
        'request': ('ui:overlay-fraction-estimate-refresh' if negative else
                    'ui:overlay-valid-fraction-soft-read'),
        'returned': ('ui:overlay-fraction-estimate-refresh' if negative else
                     'ui:overlay-valid-fraction-soft-read'),
        'positive': 'ui:revoke-saved-balances',
        'second': 'ui:overlay-valid-fraction-soft-read',
        'second-positive': 'ui:revoke-saved-balances'}, {},
        request_checks={'returned': ('request', 'test:choices', 'preserved_choices')})
    active = GrantAppEffectsJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
        settings=policy()['settings'], app_rules={baseline.MATCH_APPS[role]: (access, baseline.RULES[role])
            for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
        approval_stage='request',
        policy_reads={'baseline': (None, 'zero'), 'positive': ('baseline', 'positive'),
                      'second-positive': ('baseline', 'positive')},
        approval_stages={} if negative else {'positive': 'request', 'second-positive': 'second'},
        negative_estimates={'returned': 'request'} if negative else {})
    active.check_settings('baseline', {'ui': {'revoke_cancel': policy()}})
    active.balance = {'daily': {'seconds': 0, 'precision_seconds': 1},
        'one_time': {'seconds': 600, 'precision_seconds': 1}, 'observed_monotonic_ns': 1_000_000_000}
    return active


@pytest.mark.parametrize('fault', [None, 'extra-grant', 'precision', 'stale', 'negative-time',
                                  'changed-choice', 'missing', 'capture-replay', 'replay', 'mutation'])
def test_negative_effect_comparison_before_actual_step_reply(tmp_path, fault):
    active = effects(tmp_path, negative=True)
    captured = choice(timestamp=2)
    captured['estimate_read_bounds'] = [1_900_000_000, 2_000_000_000]
    if fault != 'missing':
        active.check_settings('request', {'ui': {'valid_choice': captured}})
    if fault == 'capture-replay':
        with pytest.raises(EvidenceError, match='replay'):
            active.check_settings('request', {'ui': {'valid_choice': captured}})
        return
    if fault == 'mutation':
        captured['estimate']['seconds'] = 1
        captured['request']['allow_soft'] = False
    returned = choice(estimate=665, timestamp=12)
    returned['estimate_read_bounds'] = [11_900_000_000, 12_000_000_000]
    if fault == 'extra-grant': returned['estimate']['seconds'] = 740
    if fault == 'precision': returned['estimate']['precision_seconds'] = 60
    if fault == 'stale': returned['observed_monotonic_ns'] = 125_000_000_000
    if fault == 'negative-time': returned['observed_monotonic_ns'] = 1_000_000_000
    if fault == 'changed-choice': returned['request']['allow_soft'] = False
    active.steps = [{'stage': stage} for stage in active.plan.stages[:active.plan.stages.index('returned')]]
    active.boot = 'b' * 64
    active.ui = SimpleNamespace(boot_proof=active.boot,
        observe=Mock(return_value={'valid_choice': returned}))
    active.collect_failure = Mock()
    (tmp_path / 'returned.request.json').write_text(json.dumps({'stage': 'returned', 'screenshot': None}))
    reply = tmp_path / 'returned.reply.json'
    active.progress.side_effect = lambda *_: pytest.fail('early reply') if reply.exists() else None
    if fault not in (None, 'mutation', 'replay'):
        with pytest.raises(EvidenceError): active.step(Mock())
        assert not reply.exists() and active.failed
        active.progress.assert_not_called()
    else:
        active.step(Mock())
        assert reply.exists() and active.steps[-1]['comparison']['no_additional_grant_with_elapsed_bounds']
        if fault == 'replay':
            with pytest.raises(EvidenceError, match='replay'):
                active.check_settings('returned', {'ui': {'valid_choice': returned}})


@pytest.mark.parametrize('fault', [None, 'before', 'intermediate', 'final', 'wide'])
def test_fresh_overlay_estimate_preserves_exact_form_and_brackets_public_edits(monkeypatch, fault):
    actual = ui_for(Node('Application'))
    before = request()
    intermediate = {**before, 'custom_text': '1.250'}
    final = dict(before)
    if fault == 'before': before['allow_soft'] = False
    if fault == 'intermediate': intermediate['approver'] = 'other-fixture-parent'
    if fault == 'final': final['allow_soft'] = False
    actual.kiosk_request_form = Mock(side_effect=[before, intermediate, final])
    actual.set_text = Mock()
    actual.snapshot_owned_target = Mock(return_value=Node('Estimated remaining time: 8m 11s'))
    monkeypatch.setattr(ui.time, 'monotonic_ns', Mock(side_effect=[
        100_000_000_000, 101_000_000_000,
        (146 if fault == 'wide' else 102) * 1_000_000_000]))
    if fault:
        with pytest.raises(ui.UiError): actual._kiosk_valid_choice('overlay-fraction-estimate-refresh')
        if fault == 'before': actual.set_text.assert_not_called()
    else:
        value = actual._kiosk_valid_choice('overlay-fraction-estimate-refresh')
        assert value['request'] == before
        assert value['estimate_read_bounds'] == [100_000_000_000, 102_000_000_000]
        assert value['observed_monotonic_ns'] == 102_000_000_000
        assert actual.set_text.call_args_list == [
            (('kiosk-custom-duration', '1.250'),), (('kiosk-custom-duration', '1.25'),)]


@pytest.mark.parametrize('fault', [None, 'missing', 'wrong-end', 'bool', 'wide', 'precision', 'choice'])
def test_fresh_overlay_estimate_decoder_requires_calculation_bracket(monkeypatch, fault):
    operation = 'overlay-fraction-estimate-refresh'
    value = choice(estimate=491, timestamp=102)
    value['estimate_read_bounds'] = [100_000_000_000, 102_000_000_000]
    if fault == 'missing': value.pop('estimate_read_bounds')
    if fault == 'wrong-end': value['estimate_read_bounds'][1] -= 1
    if fault == 'bool': value['estimate_read_bounds'][0] = True
    if fault == 'wide': value['estimate_read_bounds'][0] = 1
    if fault == 'precision': value['estimate']['precision_seconds'] = 60
    if fault == 'choice': value['request']['allow_soft'] = False
    observer = UiObservations(Mock())
    observer.boot_guard = 'b' * 64
    observer.call = Mock(return_value=(json.dumps({'operation': operation, 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'b' * 64,
        'valid_choice': value}).encode(), []))
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
    else:
        assert observer.observe(operation)['valid_choice'] == value


@pytest.mark.parametrize('fault', [None, 'wrong-capture', 'missing', 'replay', 'mutation'])
def test_repeated_positive_reads_bind_distinct_immutable_approval_estimates(tmp_path, fault):
    active = effects(tmp_path)
    first = choice(timestamp=2)
    active.check_settings('request', {'ui': {'valid_choice': first}})
    active.check_settings('positive', {'ui': {'revoke_cancel': policy(grant=665, timestamp=12)}})
    second = choice(estimate=740, timestamp=20)
    if fault != 'missing': active.check_settings('second', {'ui': {'valid_choice': second}})
    if fault == 'mutation': second['estimate']['seconds'] = 1
    if fault == 'wrong-capture': active.effects_approvals['second-positive'] = 'request'
    observed = {'ui': {'revoke_cancel': policy(grant=730, timestamp=30)}}
    if fault in ('wrong-capture', 'missing'):
        with pytest.raises(EvidenceError): active.check_settings('second-positive', observed)
    else:
        active.check_settings('second-positive', observed)
        assert observed['comparison']['positive_grant_with_elapsed_bounds']
        if fault == 'replay':
            with pytest.raises(EvidenceError, match='replay'): active.check_settings('second-positive', observed)


@pytest.mark.parametrize('operation', ['kiosk-long-included-duration-select',
                                     'overlay-long-approver-select', 'overlay-long-request-read'])
@pytest.mark.parametrize('fault', [None, 'wrong-child', 'wrong-duration', 'soft', 'text'])
def test_new_finite_transition_shapes_use_real_decoder(operation, fault):
    value = choice(seconds=600, estimate=600, timestamp=2, overlay=operation.startswith('overlay-'))
    if fault == 'wrong-child': value['request']['child'] = 'existing-fixture-child'
    if fault == 'wrong-duration': value['request']['duration_seconds'] = 75
    if fault == 'soft': value['request']['allow_soft'] = False
    if fault == 'text': value['request']['custom_text'] = '1.25'
    raw = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
           'boot_sha256': 'b' * 64, 'valid_choice': value}
    observer = UiObservations(Mock())
    observer.boot_guard = 'b' * 64
    observer.call = Mock(return_value=(json.dumps(raw).encode(), []))
    if fault:
        with pytest.raises(EvidenceError, match='ui:'): observer.observe(operation)
    else:
        assert observer.observe(operation)['valid_choice'] == value


@pytest.mark.parametrize('surface,before,after', [('kiosk', 600, 75), ('overlay', 75, 600),
    ('unknown', 75, 600), ('kiosk', True, 600), ('kiosk', 75, 600.0)])
def test_continuation_refuses_unsupported_values_before_discovery(surface, before, after):
    with pytest.raises(EvidenceError, match='continuation'):
        continued_request(surface=surface, initial_seconds=before, duration_seconds=after)


def continued_form(overlay, fault=None):
    actual, selector, _choices, _expected = accounts_form('approver')
    # Start with Casey on the overlay; the operation must explicitly select Jamie.
    if not overlay:
        selector.setValue('1000')
        selector.setValue.reset_mock()
    form = actual.find_id('kiosk-request-form')
    for node in form.children:
        if node.identity != 'kiosk-screen-limit-notice': node.states.add('sensitive')
        else: node.states.discard('showing')
    actual.find_id('kiosk-duration-1800').states.discard('pressed')
    actual.find_id('kiosk-duration-custom').states.add('pressed')
    soft = actual.find_id('kiosk-soft-apps-toggle')
    if fault != 'soft': soft.states.add('checked')
    custom = Node(identity='kiosk-custom-duration', states=('showing', 'visible', 'sensitive', 'editable'))
    custom.value = ('10' if overlay else '1.25') if fault != 'wrong-before' else '2'
    custom.get_text_iface = lambda: SimpleNamespace(get_character_count=lambda: len(custom.value),
        get_text=lambda start, end: custom.value[start:end])
    status = Node('Estimated remaining time: 10m', identity='kiosk-request-status')
    for node in (custom, status): node.parent = form; form.children.append(node)
    actual.api.Text = SimpleNamespace(get_character_count=lambda iface: iface.get_character_count(),
        get_text=lambda iface, start, end: iface.get_text(start, end))
    actual.find_id('kiosk-duration-custom').action.do_action.side_effect = lambda *_: True
    actual.require_child_overlay_session = Mock()
    if overlay:
        actual.api.get_desktop(0).identity = ui.CHILD_APPLICATION
        actual.find_id('kiosk-child-selector').states.discard('sensitive')
        original = selector.setValue.side_effect
        def select(value):
            result = original(value)
            actual.find_id('kiosk-child-selector').states.discard('sensitive')
            return result
        selector.setValue.side_effect = select
    return actual, selector, custom


@pytest.mark.parametrize('overlay', [False, True])
@pytest.mark.parametrize('fault', [None, 'soft', 'wrong-before'])
def test_finite_transition_runs_real_form_reader_and_canonical_input(monkeypatch, overlay, fault):
    actual, selector, custom = continued_form(overlay, fault)
    operation = 'overlay-long-approver-select' if overlay else 'kiosk-long-included-duration-select'
    if fault:
        with pytest.raises(ui.UiError): actual.run(operation, '')
        selector.setValue.assert_not_called()
        custom.setText.assert_not_called()
        actual.find_id('kiosk-duration-custom').action.do_action.assert_not_called()
    else:
        result = actual.run(operation, '')
        assert result['valid_choice']['request'] == request(seconds=600, overlay=overlay)
        if overlay: selector.setValue.assert_called_once_with('1000')
        else: custom.setText.assert_called_once_with('10')
        observer = UiObservations(Mock())
        observer.boot_guard = 'b' * 64
        observer.call = Mock(return_value=(json.dumps({
            **result, 'boot_sha256': 'b' * 64}).encode(), []))
        assert observer.observe(operation) == result


@pytest.mark.parametrize('fault', [None, 'wrong-owner', 'wrong-choice'])
def test_refresh_runs_real_overlay_text_recipient_guard_before_input(monkeypatch, fault):
    actual, selector, custom = continued_form(True)
    selector.setValue('1000')
    custom.value = '1.25'
    actual.find_id('kiosk-request-status').name = 'Estimated remaining time: 8m 11s'
    if fault == 'wrong-owner': actual.api.get_desktop(0).identity = ui.KIOSK_APPLICATION
    if fault == 'wrong-choice': actual.find_id('kiosk-soft-apps-toggle').states.discard('checked')
    if fault:
        with pytest.raises(ui.UiError): actual.run('overlay-fraction-estimate-refresh', '')
        custom.setText.assert_not_called()
    else:
        result = actual.run('overlay-fraction-estimate-refresh', '')
        assert result['valid_choice']['request'] == request()
        assert actual.text_overlay is True
        assert [call.args for call in custom.setText.call_args_list] == [('1.250',), ('1.25',)]
        start, end = result['valid_choice']['estimate_read_bounds']
        assert 0 < start <= end == result['valid_choice']['observed_monotonic_ns']
        observer = UiObservations(Mock())
        observer.boot_guard = 'b' * 64
        observer.call = Mock(return_value=(json.dumps({
            **result, 'boot_sha256': 'b' * 64}).encode(), []))
        assert observer.observe('overlay-fraction-estimate-refresh') == result


@pytest.mark.parametrize('fault', [None, 'same-challenge', 'missing-form', 'wrong-form', 'failed'])
def test_repeat_long_native_approval_needs_new_challenge_and_completed_fresh_request(monkeypatch, fault):
    observer = UiObservations(Mock())
    observer.boot_guard = 'c' * 64
    observer.mate_approval_index = 4
    observer.mate_rejection = False
    observer.challenges.add('a' * 64)
    observer.challenge_failed = fault == 'failed'
    observer.last_mate_operation = ('kiosk-long-request-soft-read' if fault not in
                                    ('missing-form', 'wrong-form') else
                                    'kiosk-valid-fraction-soft-read' if fault == 'wrong-form' else None)
    identity = ('a' if fault == 'same-challenge' else 'b') * 64
    def call(_args, operation, **kwargs):
        return json.dumps({'operation': operation, 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'c' * 64,
            'approval': {'challenge_id': identity,
                         'request': dict(ui.LONG_MATE_REQUEST)}}).encode(), []
    observer.call = Mock(side_effect=call)
    if fault:
        with pytest.raises(EvidenceError, match='ui:'): observer.observe('kiosk-long-mate-open')
        with pytest.raises(EvidenceError, match='ui:'): observer.observe('kiosk-long-mate-open')
    else:
        for operation in ui.LONG_MATE_ORDER[:3]: observer.observe(operation)
        assert observer.mate_approval_identity == identity and observer.mate_approval_index == 3
        assert observer.challenges == {'a' * 64, 'b' * 64}


@pytest.mark.parametrize('fault', [None, 'wrong-daily', 'zero', 'missing', 'stale'])
def test_overlay_estimate_uses_independent_positive_public_countdown(tmp_path, fault):
    active = baseline.BaselineJourney(SimpleNamespace(directory=tmp_path), Mock(), actions={'native-verify': Mock()})
    active.balance = {'daily': {'seconds': 1 if fault == 'wrong-daily' else 0, 'precision_seconds': 1},
                      'one_time': {'seconds': 0, 'precision_seconds': 1}, 'observed_monotonic_ns': 1_000_000_000}
    active.countdown_baselines['kiosk-first-new-estimate'] = (600, 2_000_000_000)
    value = {'child': 'fixture-child', 'surface': 'desktop', 'present': True,
             'text': '00:08' if fault != 'zero' else '0',
             'stable_ms': 0, 'observed_monotonic_ns': (200 if fault == 'stale' else 100) * 1_000_000_000}
    if fault == 'missing': active.countdown_baselines.clear()
    if fault:
        with pytest.raises(EvidenceError): active.check_settings('remaining-countdown', {'ui': {'countdown': value}})
    else:
        active.check_settings('remaining-countdown', {'ui': {'countdown': value}})
        captured = deepcopy(active.balance)
        value['text'] = '0:01'
        assert active.balance == captured and active.balance['one_time']['seconds'] >= 480
        refreshed = choice(estimate=570, timestamp=110)
        refreshed['estimate_read_bounds'] = [109_000_000_000, 110_000_000_000]
        active.check_settings('overlay-approval-open-estimate', {'ui': {'valid_choice': refreshed}})


@pytest.mark.parametrize('fault', [None, 'changed', 'missing', 'replay', 'mutation'])
def test_remembered_valid_choices_compare_across_surfaces_with_local_selectors(tmp_path, monkeypatch, fault):
    from request_composition import KioskRequestJourney
    plan = JourneyPlan('transfer', 'transfer', {
        'origin': 'ui:overlay-valid-fraction-soft-read',
        'destination': 'ui:kiosk-valid-fraction-soft-read'}, {},
        request_transfer_checks={'destination': 'origin'})
    active = KioskRequestJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    monkeypatch.setattr(active, 'check_estimate', lambda *_: None)
    original = choice()
    if fault != 'missing': active.check_settings('origin', {'ui': {'valid_choice': original}})
    if fault == 'mutation': original['request']['custom_text'] = '10'
    returned = choice(overlay=False)
    if fault == 'changed': returned['request']['approver'] = 'other-fixture-parent'
    observed = {'ui': {'valid_choice': returned}}
    if fault in ('changed', 'missing'):
        with pytest.raises(EvidenceError): active.check_settings('destination', observed)
    else:
        active.check_settings('destination', observed)
        assert observed['comparison']['shared_child_choices_local_approver']
        if fault == 'replay':
            with pytest.raises(EvidenceError, match='replay'): active.check_settings('destination', observed)


def test_real_recorder_constructor_preserves_finite_timeout_and_actions(tmp_path):
    recorder = MagicMock(assertion=Mock())
    recorder.artifact.return_value = 'artifact'
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    def worker(**options):
        active = options['guarded_observe'].__self__
        assert type(active) is baseline.BaselineJourney and active.plan is baseline.PLAN
        assert set(active.actions) == {'native-verify'}
        assert options['timeout'] == 1800 and options['authenticate'] is True
        raise EvidenceError('synthetic-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-stop'):
        record_installed_journey(recorder, context, baseline.PLAN, journey_type=baseline.BaselineJourney)
    recorder.assertion.assert_not_called()
