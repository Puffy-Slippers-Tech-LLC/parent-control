"""Overlay surface guards, finite public choices and worker/recorder boundaries.

Parallelism: process-local doubles, private tmp_path evidence, bounded waited
Perl children; no live displays, VMs, sockets, shared files or caches.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import accessible_ui as a
import check_e2e_overlay_valid_choices as check
from installed_journey import JourneyPlan, matched_screens
from overlay_valid_choices import PLAN, OverlayValidChoicesJourney
from parent_setup_qualification import OverlayValidChoicesQualification, KioskEntryQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import accounts_form
from tests.support.perl import run_perl
from ui_observations import UiObservations, RequestObservation, OPERATION_LABELS


def test_real_recorder_startup_accepts_plan_and_actions(tmp_path, monkeypatch):
    import installed_journey
    recorder = MagicMock()
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(), guestfs=Mock(),
        commands=Mock(), verified=SimpleNamespace(inputs={}))
    def worker(**kw):
        assert kw['guarded_observe'].__self__.plan is PLAN
        assert set(kw['guarded_observe'].__self__.actions) == {'native-refuse', 'native-verify'}
        return {'shutdown_verified': True, 'worker_stopped': True, 'callback_closed': True, 'outcome': 'passed'}
    context.run_worker = worker
    monkeypatch.setattr(OverlayValidChoicesJourney, 'validate', lambda self: [])
    installed_journey.record_installed_journey(recorder, context, PLAN,
        journey_type=OverlayValidChoicesJourney)
    context.credentials.provision.assert_called_once()


def child_session(monkeypatch):
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1001))
    monkeypatch.setattr(a.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(a.os, 'geteuid', lambda: 1001)
    monkeypatch.setattr(a, 'require_active_launch_session', Mock())


def overlay(monkeypatch):
    child_session(monkeypatch)
    ui, selector, choices, _ = accounts_form('approver')
    choices.children[0].action.do_action(0)
    application = ui.api.get_desktop(0)
    application.identity = a.CHILD_APPLICATION
    form = ui.find_id('kiosk-request-form')
    child = ui.find_id('kiosk-child-selector')
    child.states.discard('sensitive')
    status = Node('Estimated time remaining if approved: 45m', identity='kiosk-request-status')
    custom = Node(identity='kiosk-custom-duration', states=('visible', 'sensitive', 'editable'))
    custom.value = '1.25'
    custom.get_text_iface = lambda: SimpleNamespace(
        get_character_count=lambda: len(custom.value), get_text=lambda start, end: custom.value[start:end])
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: text.get_character_count(),
                                 get_text=lambda text, start, end: text.get_text(start, end))
    for node in (status, custom):
        node.parent = form
        form.children.append(node)
    for value in (300, 900, 1800, 3600, 7200, 14400, 0, 'custom'):
        target = ui.find_id(f'kiosk-duration-{value}')
        def select(_index, value=value):
            for node in form.children:
                if node.identity.startswith('kiosk-duration-'):
                    node.states.discard('pressed')
            ui.find_id(f'kiosk-duration-{value}').states.add('pressed')
            if value == 'custom': custom.states.add('showing')
            else: custom.states.discard('showing')
            status.name = ('If approved, access until midnight.' if value == 0 else
                'Estimated time remaining if approved: 16m 15s' if value == 'custom' else
                'Estimated time remaining if approved: 20m')
            return True
        target.action.do_action.side_effect = select
    soft = ui.find_id('kiosk-soft-apps-toggle')
    soft.action.do_action.side_effect = lambda _: soft.states.symmetric_difference_update({'checked'}) or True
    return ui, application, child, status, custom


def test_valid_choices_round_trip_through_real_decoder_and_diagnostics(monkeypatch, capsys):
    ui, _, child, _, _ = overlay(monkeypatch)
    operations = ('overlay-valid-preset-select', 'overlay-valid-preset-read',
        'overlay-valid-custom-open', 'overlay-valid-fraction-read', 'overlay-valid-rest-select',
        'overlay-valid-rest-read', 'overlay-valid-soft-select', 'overlay-valid-soft-read',
        'overlay-valid-excluded-select', 'overlay-valid-excluded-read')
    for operation in operations:
        ui.input_uncertain = False  # Independent observer process at each boundary.
        result = ui.run(operation, '')
        diagnostics = capsys.readouterr().out.encode()
        raw = diagnostics + (json.dumps(result) + '\n').encode()
        def call(*_args, on_output, **_kwargs):
            for start in range(0, len(raw), 19): on_output(raw[start:start + 19])
            return raw
        observer = UiObservations(SimpleNamespace(call=call, commands=SimpleNamespace(progress=None)))
        observed = observer.observe(operation)
        if operation in a.OVERLAY_VALID_REQUESTS:
            request = RequestObservation.from_request(observed['valid_choice']['request'], operation=operation)
            assert request.surface == 'child-overlay' and not request.child_selector_enabled
            assert request.approver == 'fixture-parent'
    child.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['station', 'unlocked', 'wrong-child', 'prompt', 'disabled', 'duplicate', 'uncertain'])
def test_overlay_input_refuses_before_action(monkeypatch, fault):
    ui, application, child, _, _ = overlay(monkeypatch)
    target = ui.find_id('kiosk-duration-300')
    if fault == 'station': application.identity = a.KIOSK_APPLICATION
    if fault == 'unlocked': child.states.add('sensitive')
    if fault == 'wrong-child': child.children[0].identity = 'kiosk-child-selected-1002'
    if fault == 'prompt': ui.handle_system_prompt = Mock(side_effect=a.UiError('ui:prompt'))
    if fault == 'disabled': target.states.discard('sensitive')
    if fault == 'duplicate': ui.find_id('kiosk-request-form').children.append(Node(identity=target.identity))
    if fault == 'uncertain': ui.input_uncertain = True
    with pytest.raises(a.UiError): ui.run('overlay-valid-preset-select', '')
    target.action.do_action.assert_not_called()
    child.action.do_action.assert_not_called()


def test_live_wrong_surface_and_fixed_child_refusals_release_no_input(monkeypatch):
    ui, _, child, _, _ = overlay(monkeypatch)
    ui.run('overlay-valid-refusals', '')
    child.action.do_action.assert_not_called()
    ui.find_id('kiosk-duration-300').action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'station', 'prompt', 'uncertain'])
def test_overlay_cancel_uses_shared_owned_guard_once(monkeypatch, fault):
    ui, application, _, _, _ = overlay(monkeypatch)
    target = ui.find_id('kiosk-request-cancel')
    if fault == 'station': application.identity = a.KIOSK_APPLICATION
    if fault == 'prompt': ui.handle_system_prompt = Mock(side_effect=a.UiError('ui:prompt'))
    if fault == 'uncertain': target.action.do_action.side_effect = TimeoutError()
    if fault:
        with pytest.raises((a.UiError, TimeoutError)): ui.run('overlay-request-cancel', '')
    else: ui.run('overlay-request-cancel', '')
    assert target.action.do_action.call_count == (0 if fault in ('station', 'prompt') else 1)
    if fault == 'uncertain':
        with pytest.raises(a.UiError): ui.run('overlay-request-cancel', '')
        target.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'wrong-account', 'submission'])
def test_native_child_command_binds_actual_overlay_account_and_single_input(monkeypatch, fault):
    child_session(monkeypatch)
    if fault == 'wrong-account': monkeypatch.setattr(a.os, 'getuid', lambda: 1002)
    ui = ui_for(Node())
    ui.desktop_result = Mock()
    ui.native_app_closed = Mock(return_value=True)
    submit = Mock(side_effect=TimeoutError() if fault == 'submission' else None)
    monkeypatch.setattr(a.subprocess, 'run', submit)
    if fault:
        with pytest.raises((a.UiError, TimeoutError)): ui.run('overlay-native-command-launch', '')
    else: ui.run('overlay-native-command-launch', '')
    assert submit.call_count == (0 if fault == 'wrong-account' else 1)
    if fault != 'wrong-account':
        ui.desktop_result.assert_called_once_with(a.CHILD, 'success')
        with pytest.raises(a.UiError): ui.run('overlay-native-command-launch', '')
        submit.assert_called_once()


def test_selector_snapshot_plan_and_account_registration(monkeypatch):
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kw: calls.append(kw) or 0)
    assert check.main() == 0
    assert calls[0]['challenge_profile'] == 'overlay-valid-choices'
    context = SimpleNamespace()
    journey = OverlayValidChoicesQualification.journey(context, Mock())
    assert journey.plan is PLAN and context.installed_snapshot.startswith('onpc-v')
    assert OverlayValidChoicesQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert set(journey.actions) == {'native-refuse', 'native-verify'}
    operations = {tag[3:] for tag in PLAN.screen_tags.values() if tag.startswith('ui:')}
    assert operations <= a.OPERATIONS and operations <= OPERATION_LABELS.keys()
    assert a.OVERLAY_VALID_OPERATIONS | a.OVERLAY_NATIVE_OPERATIONS <= a.CHILD_DESKTOP_OPERATIONS
    assert not (a.OVERLAY_VALID_OPERATIONS & a.KIOSK_SESSION_OPERATIONS)


@pytest.mark.parametrize('actual', [500, 920, 976, 980])
def test_overlay_estimate_is_bounded_by_independent_balance_and_elapsed_time(tmp_path, actual):
    journey = OverlayValidChoicesJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.balance = {'daily': {'seconds': 900, 'precision_seconds': 1},
                       'one_time': {'seconds': 0, 'precision_seconds': 1},
                       'observed_monotonic_ns': 1_000_000_000}
    observed = {'ui': {'valid_choice': {'request': {'surface': 'child-overlay', 'duration_seconds': 75},
        'estimate': {'kind': 'fixed', 'seconds': actual}, 'observed_monotonic_ns': 61_000_000_000}}}
    if actual in (920, 976): journey.check_estimate(observed)
    else:
        with pytest.raises(EvidenceError, match='estimate-bounds'): journey.check_estimate(observed)


@pytest.mark.parametrize('fault', [None, 'changed-window', 'changed-draft', 'missing', 'replay'])
def test_real_recorder_step_compares_renamed_activity_before_reply(tmp_path, fault):
    plan = JourneyPlan('independent', 'independent', {
        'before': 'ui:overlay-native-activity', 'after': 'ui:overlay-native-activity'}, {},
        activity_checks={'after': ('before', 'same')})
    journey = OverlayValidChoicesJourney(SimpleNamespace(directory=tmp_path), Mock(), plan, actions={})
    value = {'binding': 'native-primary', 'pid': 123, 'endpoint': [':1.50', '/accessible/1'],
             'state': {'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft', 'score': 'Moves: 0; token: 0'}}
    if fault != 'missing': journey.check_activity('before', {'ui': {'activity': deepcopy(value)}})
    if fault == 'changed-window': value['endpoint'][1] = '/replacement'
    if fault == 'changed-draft': value['state']['draft'] = 'changed'
    if fault == 'replay': journey.check_activity('after', {'ui': {'activity': value}})
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}, {'stage': 'before'}]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'overlay-native-activity', 'outcome': 'passed', 'interface': 'AT-SPI', 'activity': value}))
    (tmp_path / 'after.request.json').write_text(json.dumps({'stage': 'after', 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, a.UiError)): journey.step(Mock())
        assert not (tmp_path / 'after.reply.json').exists()
    else:
        journey.step(Mock())
        assert (tmp_path / 'after.reply.json').exists()
        assert journey.steps[-1]['comparison']['same_window'] is True


@pytest.mark.parametrize('fault', ['', *list(PLAN.screen_tags)])
def test_actual_worker_order_titles_and_failure_stop(tmp_path, fault):
    program = r'''
use strict; use warnings; use JSON::PP;
our @events; our $fault = shift @ARGV;
our $declared = decode_json(shift @ARGV); our $challenges = decode_json(shift @ARGV);
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub record_info { push @main::events, ['marker', $_[0]] }
sub get_var { '1' } sub get_required_var { 'synthetic-secret' }
sub type_password { push @main::events, ['password'] }
sub send_key { push @main::events, ['key', $_[0]] }
sub type_string { push @main::events, ['text', $_[0]] }
package main; require onpc_request_flow;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_request_flow::overlay_valid_choices(sub {
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
    }, $declared, $challenges); 1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    result = json.loads(run_perl(program, fault, json.dumps(PLAN.invocations), json.dumps(PLAN.challenges)).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'seen']
    expected = list(PLAN.screen_tags)
    assert bool(result['ok']) == (not fault), result['error']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if fault: assert ['finish'] not in result['events']
    else:
        details = [{'title': event[1], 'result': 'ok'} for event in result['events'] if event[0] == 'marker']
        proofs = {event[1]: event[2] for event in result['events'] if event[0] == 'challenge'}
        observations = [{'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
            'operation': tag.split(':', 1)[1], 'outcome': 'passed',
            'interface': 'AT-SPI' if tag.startswith('ui:') else 'system session'},
            **({'challenge': proofs[stage]} if stage in proofs else {})}
            for stage, tag in PLAN.screen_tags.items()]
        (tmp_path / 'testresults').mkdir()
        (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
        assert len(matched_screens(tmp_path, PLAN, observations)) == len(expected)
        assert sum(event[0] == 'password' for event in result['events']) == 2
        assert [event[1] for event in result['events'] if event[0] == 'text'] == ['1.25']
