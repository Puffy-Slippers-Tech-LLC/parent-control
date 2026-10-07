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
import check_e2e_overlay_choices as choices_check
from installed_journey import JourneyPlan, matched_screens
from overlay_valid_choices import PLAN, OverlayValidChoicesJourney
from overlay_choices import PLAN as CHOICES_PLAN, OverlayChoicesJourney
from overlay_prompt import PLAN as PROMPT_PLAN, OverlayPromptJourney
from overlay_approved_exit import PLAN as APPROVED_PLAN, OverlayApprovedExitJourney
from overlay_license import PLAN as LICENSE_PLAN, BROWSER_LINKS_PLAN, INFORMATION_PLAN, OverlayLicenseJourney
from overlay_about import PLAN as ABOUT_CASE_PLAN
from request_flow import prepared_request
from parent_setup_qualification import OverlayValidChoicesQualification, KioskEntryQualification
from parent_setup_qualification import OverlayChoicesQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import accounts_form
from tests.support.perl import run_perl
from ui_observations import UiObservations, RequestObservation, OPERATION_LABELS


@pytest.mark.parametrize('plan,journey_type', [(PLAN, OverlayValidChoicesJourney),
                                            (CHOICES_PLAN, OverlayChoicesJourney),
                                            (PROMPT_PLAN, OverlayPromptJourney),
                                            (APPROVED_PLAN, OverlayApprovedExitJourney),
                                            (LICENSE_PLAN, OverlayLicenseJourney),
                                            (BROWSER_LINKS_PLAN, OverlayLicenseJourney),
                                            (INFORMATION_PLAN, OverlayLicenseJourney)])
def test_real_recorder_startup_accepts_plan_and_actions(tmp_path, monkeypatch, plan, journey_type):
    import installed_journey
    recorder = MagicMock()
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(), guestfs=Mock(),
        commands=Mock(), verified=SimpleNamespace(inputs={}))
    def worker(**kw):
        assert kw['guarded_observe'].__self__.plan is plan
        assert set(kw['guarded_observe'].__self__.actions) == (
            set() if plan in (LICENSE_PLAN, BROWSER_LINKS_PLAN, INFORMATION_PLAN, PROMPT_PLAN)
            else {'native-refuse', 'native-verify'})
        return {'shutdown_verified': True, 'worker_stopped': True, 'callback_closed': True, 'outcome': 'passed'}
    context.run_worker = worker
    monkeypatch.setattr(journey_type, 'validate', lambda self: [])
    installed_journey.record_installed_journey(recorder, context, plan,
        journey_type=journey_type)
    context.credentials.provision.assert_called_once()


def child_session(monkeypatch):
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1001))
    monkeypatch.setattr(a.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(a.os, 'geteuid', lambda: 1001)
    monkeypatch.setattr(a, 'require_active_launch_session', Mock())


def overlay(monkeypatch):
    child_session(monkeypatch)
    ui, selector, choices, _ = accounts_form('approver')
    selector.setValue('1000')
    selector.setValue.reset_mock()
    application = ui.api.get_desktop(0)
    application.identity = a.CHILD_APPLICATION
    form = ui.find_id('kiosk-request-form')
    child = ui.find_id('kiosk-child-selector')
    child.states.discard('sensitive')
    child.value = '1001'
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


@pytest.mark.parametrize('fault', ['', 'selection', 'duration', 'soft'])
def test_restored_shared_choices_select_local_approver_without_rewriting_choices(monkeypatch, fault):
    ui, _, child, _, custom = overlay(monkeypatch)
    selector = ui.find_id('kiosk-approver-selector')
    commit = selector.setValue.side_effect
    commit('1010')  # The fresh overlay's local default is Casey, unlike kiosk.
    child.states.discard('sensitive')
    selector.setValue.reset_mock()
    for seconds in (300, 900, 1800, 3600, 7200, 14400, 0, 'custom'):
        ui.find_id(f'kiosk-duration-{seconds}').states.discard('pressed')
    ui.find_id('kiosk-duration-custom').states.add('pressed')
    custom.states.add('showing')
    soft = ui.find_id('kiosk-soft-apps-toggle')
    soft.states.add('checked')

    def select(value):
        if fault != 'selection':
            commit(value)
        child.states.discard('sensitive')
        if fault == 'duration': custom.value = '2'
        if fault == 'soft': soft.states.discard('checked')

    selector.setValue.side_effect = select
    if fault:
        with pytest.raises(a.UiError):
            ui.run('overlay-flow-approver-select', '')
    else:
        result = ui.run('overlay-flow-approver-select', '')
        request = result['valid_choice']['request']
        assert request['approver'] == 'fixture-parent'
        assert request['child'] == 'fixture-child'
        assert request['duration_seconds'] == 75 and request['custom_text'] == '1.25'
        assert request['allow_soft'] is True
    selector.setValue.assert_called_once_with('1000')
    custom.setText.assert_not_called()
    soft.setValue.assert_not_called()
    soft.action.do_action.assert_not_called()
    child.setValue.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'persistent', 'wrong-owner', 'prompt', 'disabled'])
def test_overlay_approver_reacquires_stale_preflight_before_any_input(monkeypatch, fault):
    ui, application, child, _, _ = overlay(monkeypatch)
    # Keep the OS oracle independent of UI choices and local to this synthetic
    # fixture; the development host does not own these fixture accounts.
    monkeypatch.setattr(ui, 'interactive_approver_uids',
                        Mock(return_value={'1000', '1010'}))
    selector = ui.find_id('kiosk-approver-selector')
    choices = ui.find_id('kiosk-approver-choices', showing=False)
    for target in choices.children:
        target.action.do_action.reset_mock()
    commit = selector.setValue.side_effect

    def select(index):
        commit(index)
        child.states.discard('sensitive')
        return True

    selector.setValue.side_effect = select
    stale = Node('private stale content', states=('defunct',))
    stale.parent = application
    application.children.append(stale)
    original_nodes = ui.nodes
    reads = []
    now = [0.0]
    ui.timeout = .4
    monkeypatch.setattr(a, 'time', SimpleNamespace(
        monotonic=lambda: now[0], monotonic_ns=lambda: int(now[0] * 1e9),
        sleep=lambda seconds: now.__setitem__(0, now[0] + seconds)))

    def nodes(*args, **kwargs):
        reads.append(selector.setValue.call_count)
        if len(reads) == 2 and fault != 'persistent':
            application.children.remove(stale)
            if fault == 'wrong-owner': ui.owner_pids = lambda: {999}
            if fault == 'prompt': ui.handle_system_prompt = Mock(side_effect=a.UiError('ui:prompt'))
            if fault == 'disabled': selector.states.discard('sensitive')
        yield from original_nodes(*args, **kwargs)

    monkeypatch.setattr(ui, 'nodes', nodes)
    if fault:
        with pytest.raises(a.UiError, match={
            'persistent': 'stale-request-form', 'wrong-owner': 'wrong-owner',
            'prompt': 'ui:prompt', 'disabled': 'kiosk-account-unavailable'}[fault]):
            ui.run('overlay-valid-approver-select', '')
        selector.action.do_action.assert_not_called()
        choices.children[0].action.do_action.assert_not_called()
        assert ui.input_uncertain
    else:
        result = ui.run('overlay-valid-approver-select', '')
        request = RequestObservation.from_request(result['valid_choice']['request'],
                                                 operation='overlay-valid-approver-select')
        assert request.approver == 'fixture-parent' and not request.child_selector_enabled
        selector.setValue.assert_called_once_with('1000')
        selector.action.do_action.assert_not_called()
        choices.children[0].action.do_action.assert_not_called()
    assert reads[:2] == [0, 0]
    child.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['station', 'unlocked', 'wrong-child', 'prompt', 'disabled', 'duplicate', 'uncertain'])
def test_overlay_input_refuses_before_action(monkeypatch, fault):
    ui, application, child, _, _ = overlay(monkeypatch)
    target = ui.find_id('kiosk-duration-300')
    if fault == 'station': application.identity = a.KIOSK_APPLICATION
    if fault == 'unlocked': child.states.add('sensitive')
    if fault == 'wrong-child': child.value = '1002'
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
        'operation': 'overlay-native-activity', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', 'activity': value}))
    (tmp_path / 'after.request.json').write_text(json.dumps({'stage': 'after', 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, a.UiError)): journey.step(Mock())
        assert not (tmp_path / 'after.reply.json').exists()
    else:
        journey.step(Mock())
        assert (tmp_path / 'after.reply.json').exists()
        assert journey.steps[-1]['comparison']['same_window'] is True


@pytest.mark.parametrize('plan,fault', [(plan, fault) for plan in (
    PLAN, CHOICES_PLAN, PROMPT_PLAN, APPROVED_PLAN, LICENSE_PLAN, BROWSER_LINKS_PLAN, INFORMATION_PLAN, ABOUT_CASE_PLAN)
                                      for fault in ('', *plan.screen_tags)])
def test_actual_worker_order_titles_and_failure_stop(tmp_path, plan, fault):
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
        my ($stage, $shot, $input) = @_; push @events, ['seen', $stage]; die 'refused' if $stage eq $fault;
        if (defined($input)) {
            $input->({stage => $stage, token => 'a' x 32, source => 'a' x 64,
                       child => 'child', binding => 'overlay-approve', values => ['ret']});
        }
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
    if plan is ABOUT_CASE_PLAN:
        program = program.replace('require onpc_request_flow;', 'require onpc_parent_about;').replace(
            'onpc_request_flow::overlay_valid_choices(', 'onpc_parent_about::run_overlay(')
    elif plan is APPROVED_PLAN:
        program = program.replace('onpc_request_flow::overlay_valid_choices(',
                                  'onpc_request_flow::overlay_prompt(').replace(
                                      '}, $declared, $challenges);', '}, $declared, $challenges, "approval");')
    else:
        program = program.replace('onpc_request_flow::overlay_valid_choices(',
                                  'onpc_request_flow::' + plan.worker_mode + '(')
    result = json.loads(run_perl(program, fault, json.dumps(plan.invocations), json.dumps(plan.challenges)).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'seen']
    expected = list(plan.screen_tags)
    assert bool(result['ok']) == (not fault), result['error']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if fault: assert ['finish'] not in result['events']
    else:
        details = [{'title': event[1], 'result': 'ok'} for event in result['events'] if event[0] == 'marker']
        proofs = {event[1]: event[2] for event in result['events'] if event[0] == 'challenge'}
        observations = [{'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
            'operation': tag.split(':', 1)[1], 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider' if tag.startswith('ui:') else 'system session'},
            **({'challenge': proofs[stage]} if stage in proofs else {})}
            for stage, tag in plan.screen_tags.items()]
        (tmp_path / 'testresults').mkdir()
        (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
        assert len(matched_screens(tmp_path, plan, observations)) == len(expected)
        assert sum(event[0] == 'password' for event in result['events']) == (3 if plan is APPROVED_PLAN else 2)
        assert [event[1] for event in result['events'] if event[0] == 'text'] == []
        if plan is CHOICES_PLAN:
            assert sum(event == ['key', 'esc'] for event in result['events']) == 0


@pytest.mark.parametrize('binding,value', a.KIOSK_INVALID_VALUES.items())
def test_overlay_invalid_input_decodes_exact_preserved_form(monkeypatch, capsys, binding, value):
    ui, _, _, status, custom = overlay(monkeypatch)
    ui.run('overlay-valid-custom-open', '')
    custom.value = value
    submit = ui.find_id('kiosk-request-submit')
    def validate(_):
        status.name = 'Enter a number from 0.1 to 1440 minutes.'
        return True
    submit.action.do_action.side_effect = validate
    for action in ('ready', 'submit', 'read'):
        operation = f'overlay-invalid-{binding}-{action}'
        result = ui.run(operation, '')
        raw = capsys.readouterr().out.encode() + (json.dumps(result) + '\n').encode()
        def call(*_args, on_output, **_kwargs):
            for start in range(0, len(raw), 19): on_output(raw[start:start + 19])
            return raw
        observer = UiObservations(SimpleNamespace(call=call, commands=SimpleNamespace(progress=None)))
        assert observer.observe(operation) == result
        request = RequestObservation.from_request(result['invalid_choice']['request'], operation=operation)
        assert request.surface == 'child-overlay' and request.child_selector_enabled is False
        assert request.duration_seconds is None and request.custom_text == value
        assert request.request_enabled and result['invalid_choice']['no_authentication'] is True
    submit.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['wrong-surface', 'wrong-child', 'unlocked-child', 'disabled',
                                  'prompt', 'prompt-after', 'no-validation', 'changed-text', 'uncertain'])
def test_overlay_invalid_submission_stops_without_replay(monkeypatch, fault):
    ui, application, child, status, custom = overlay(monkeypatch)
    ui.run('overlay-valid-custom-open', '')
    custom.value = 'abc'
    ui.timeout = .01
    submit = ui.find_id('kiosk-request-submit')
    if fault == 'wrong-surface': application.identity = a.KIOSK_APPLICATION
    if fault == 'wrong-child': child.value = '9999'
    if fault == 'unlocked-child': child.states.add('sensitive')
    if fault == 'disabled': submit.states.discard('sensitive')
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
    def validate(_):
        if fault == 'uncertain': raise RuntimeError('lost result')
        if fault != 'no-validation': status.name = 'Enter a number from 0.1 to 1440 minutes.'
        if fault == 'changed-text': custom.value = '0'
        if fault == 'prompt-after': ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
        return True
    submit.action.do_action.side_effect = validate
    with pytest.raises((a.UiError, RuntimeError)):
        ui.run('overlay-invalid-letters-submit', '')
    if fault != 'prompt':
        with pytest.raises(a.UiError, match='uncertain-input'):
            ui.kiosk_invalid_choice('overlay-invalid-letters-submit')
    assert submit.action.do_action.call_count == (0 if fault in (
        'wrong-surface', 'wrong-child', 'unlocked-child', 'disabled', 'prompt') else 1)


@pytest.mark.parametrize('fault', [None, 'wrong-surface', 'prompt', 'uncertain'])
def test_overlay_close_uses_surface_api_without_activating_cancel(monkeypatch, fault):
    ui, application, _, _, _ = overlay(monkeypatch)
    cancel = ui.find_id('kiosk-request-cancel')
    window = ui.find_id('kiosk-request-window')
    if fault == 'wrong-surface': application.identity = a.KIOSK_APPLICATION
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
    if fault == 'uncertain': window.close.side_effect = TimeoutError()
    if fault:
        with pytest.raises((a.UiError, TimeoutError)):
            ui.run('overlay-request-escape-ready', '')
    else:
        ui.run('overlay-request-escape-ready', '')
    cancel.action.do_action.assert_not_called()
    window.action.do_action.assert_not_called()
    assert window.close.call_count == (0 if fault in ('wrong-surface', 'prompt') else 1)
    if fault == 'uncertain':
        with pytest.raises(a.UiError, match='uncertain-input'):
            ui.run('overlay-request-escape-ready', '')
        window.close.assert_called_once_with()

def test_overlay_choices_registration_and_shared_open_new_bindings(monkeypatch):
    calls = []
    monkeypatch.setattr(choices_check, 'smoke', lambda **kw: calls.append(kw) or 0)
    assert choices_check.main() == 0
    assert calls[0]['challenge_profile'] == 'overlay-choices'
    context = SimpleNamespace()
    journey = OverlayChoicesQualification.journey(context, Mock())
    assert journey.plan is CHOICES_PLAN and context.installed_snapshot.startswith('onpc-v')
    assert OverlayChoicesQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    operations = {tag[3:] for tag in CHOICES_PLAN.screen_tags.values() if tag.startswith('ui:')}
    assert operations <= a.OPERATIONS and operations <= OPERATION_LABELS.keys()
    assert a.OVERLAY_INVALID_OPERATIONS.keys() <= a.CHILD_DESKTOP_OPERATIONS
    assert not (a.OVERLAY_INVALID_OPERATIONS.keys() & a.KIOSK_SESSION_OPERATIONS)
    choices = dict(child='fixture-child', approver='fixture-parent', duration_seconds=75,
                   allow_soft=True, surface='overlay')
    opened = prepared_request(prefix='open', entry='open', initial='default', **choices)
    new = prepared_request(prefix='new', entry='new', initial='selected', **choices)
    assert not any(operation == 'ui:child-command-launch' for operation in opened.values())
    assert new['new-entry-launch'] == 'ui:child-command-launch'
    assert new['new-entry-form'] == 'ui:overlay-valid-fraction-soft-read'
    assert all('child-select' not in operation for operation in (*opened.values(), *new.values()))
    assert set(CHOICES_PLAN.activity_checks) == {'activity-cancel', 'activity-escape'}


@pytest.mark.parametrize('fault', [None, 'changed-choice', 'mutated-capture', 'replay'])
def test_overlay_flow_compares_independent_preserved_choices(tmp_path, fault):
    journey = OverlayChoicesJourney(SimpleNamespace(directory=tmp_path), Mock())
    value = {'surface': 'child-overlay', 'child': 'fixture-child', 'approver': 'fixture-parent',
             'duration_seconds': 75, 'custom_text': '1.25', 'allow_soft': True}
    before = {'ui': {'valid_choice': {'request': value}}}
    journey.check_preserved_request('open-estimate', before)
    if fault == 'mutated-capture': value['allow_soft'] = False
    after = deepcopy(before)
    if fault == 'changed-choice': after['ui']['valid_choice']['request']['approver'] = 'other-fixture-parent'
    if fault == 'replay': journey.check_preserved_request('new-estimate', after)
    if fault:
        with pytest.raises(EvidenceError): journey.check_preserved_request('new-estimate', after)
    else:
        journey.check_preserved_request('new-estimate', after)
        assert after['comparison']['reproduced_choices'] is True


@pytest.mark.parametrize('field,value', [('surface', 'kiosk'), ('child_selector_enabled', True),
    ('child', 'existing-fixture-child'), ('duration_seconds', 75), ('custom_text', '1.25'),
    ('request_enabled', False), ('allow_soft', True)])
def test_overlay_invalid_decoder_refuses_wrong_projection(monkeypatch, capsys, field, value):
    ui, _, _, _, custom = overlay(monkeypatch)
    ui.run('overlay-valid-custom-open', '')
    custom.value = '0.09'
    operation = 'overlay-invalid-below-ready'
    result = ui.run(operation, '')
    capsys.readouterr()
    result['invalid_choice']['request'][field] = value
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises(EvidenceError): observer.observe(operation)
