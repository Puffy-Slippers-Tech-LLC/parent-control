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
from overlay_approved_exit import IMMEDIATE_PLAN, FLOW_REJECTION_PLAN, FLOW_CANCEL_PLAN
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
from choices_overlay_to_kiosk import PLAN as TRANSFER_PLAN, ChoicesOverlayToKioskJourney
from remembered_choices import PLAN as REMEMBERED_PLAN
from request_composition import KioskRequestJourney
from tests.support.desktop_session import RUN_PROBE
from tests.support.paths import ROOT


def transfer_request(*, overlay=True, jordan=False, remembered=False):
    short = jordan if remembered else not jordan
    return dict(surface='child-overlay' if overlay else 'kiosk', form_count=1,
        child='existing-fixture-child' if jordan else 'fixture-child',
        approver='fixture-parent' if overlay != remembered else 'other-fixture-parent',
        duration_seconds=75 if short else 150, custom_text='1.25' if short else '2.5',
        allow_soft=short, child_selector_enabled=not overlay, approver_selector_enabled=True,
        duration_enabled=True, soft_choice_enabled=True, request_enabled=True,
        cancel_enabled=True, message='', mute=None)


@pytest.mark.parametrize('case', [False, True, 'diagnosis', 'repeat', 'entry'])
def test_transfer_worker_order_titles_refusal_and_registration(tmp_path, monkeypatch, case):
    import check_e2e_choices_overlay_to_kiosk as check
    import session_control
    from parent_setup_qualification import ChoicesOverlayToKioskQualification
    from tools import test_commands
    from tools.test_storage import named_input
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
require onpc_request_flow;
my $plan = decode_json($ARGV[1]);
my $ok = eval {
    onpc_request_flow::qualify_choices_overlay_to_kiosk(sub {
        my ($stage) = @_;
        push @events, ['stage', $stage]; die 'refused' if $stage eq $action;
        for my $id (keys %{$plan->{challenges}}) {
            my ($role, $first, $second) = @{$plan->{challenges}{$id}};
            return {observed => $stage, challenge => {id => $id, role => $role,
                surface => 'gdm', check => $stage eq $first ? 'qualified' : 'rechecked'}}
                if $stage eq $first || $stage eq $second;
        }
        return {observed => $stage, station_destination => 'default-request-form'} if $stage =~ /station-branch$/;
        return {observed => $stage, ui_focused => 1} if $stage =~ /(?:greeter|list)$/;
        return {observed => $stage};
    }, $plan->{invocations}, $plan->{challenges});
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    program = program.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]]; }")
    plan = REMEMBERED_PLAN if case else TRANSFER_PLAN
    if case == 'diagnosis':
        from remembered_choices import DIAGNOSTIC_PLAN
        plan = DIAGNOSTIC_PLAN
    if case in ('repeat', 'entry'):
        import vm_probe
        capture = Mock()
        monkeypatch.setattr(vm_probe, 'reproduce_denial', capture)
        (vm_probe.repeat_remembered_return if case == 'repeat' else vm_probe.enter_remembered_return)(Mock())
        plan = capture.call_args.args[2]
        assert capture.call_args.args[3:] == ('jordan-return-entry-desktop', 'remembered-return')
        assert capture.call_args.kwargs == {'boundary_operation': 'standard-desktop'}
        assert plan.request_transfer_checks == (
            {'riley-return-transfer-read': 'riley-return-source'} if case == 'repeat' else {})
    if case:
        program = program.replace('require onpc_request_flow;', 'require onpc_remembered_choices;')
        program = program.replace('onpc_request_flow::qualify_choices_overlay_to_kiosk',
                                  'onpc_remembered_choices::repeat_return_for_diagnosis'
                                  if case == 'repeat' else 'onpc_remembered_choices::enter_return_for_diagnosis'
                                  if case == 'entry' else 'onpc_remembered_choices::run')
    binding = json.dumps({'invocations': plan.invocations, 'challenges': plan.challenges})
    result = json.loads(run_perl(program, '', binding).stdout)
    assert result['ok'], result
    events = result['events']
    assert [row[1] for row in events if row[0] == 'stage'] == list(plan.screen_tags)
    assert events.count(['secret']) == (2 if case == 'repeat' else 1 if case == 'entry'
                                      else 5 if case == 'diagnosis' else 3 if case else 4)
    for stage in plan.screen_tags:
        failed = json.loads(run_perl(program, stage, binding).stdout)
        assert not failed['ok'], failed
        assert failed['events'] == events[:events.index(['stage', stage]) + 1]
    if case is True:
        # A refusal at either old retained desktop boundary cannot affect the
        # customer case: neither boundary is visited, and all core reads remain.
        for removed in ('jordan-return-entry-desktop', 'riley-return-entry-desktop'):
            unaffected = json.loads(run_perl(program, removed, binding).stdout)
            assert unaffected['ok'] and unaffected['events'] == events
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': [
        {'title': row[1], 'result': 'ok'} for row in events if row[0] == 'title']}))
    observed = [{'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
        'operation': tag.split(':', 1)[1], 'outcome': 'passed'},
        **({'challenge': plan.challenge_at(stage)} if plan.challenge_at(stage) else {})}
        for stage, tag in plan.screen_tags.items()]
    assert [row['stage'] for row in matched_screens(tmp_path, plan, observed)] == list(plan.screen_tags)
    assert all(tag[3:] in a.OPERATIONS and tag[3:] in OPERATION_LABELS if tag.startswith('ui:')
               else tag[7:] in session_control.BINDINGS for tag in plan.screen_tags.values())
    if case:
        return
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kw: calls.append(kw) or 0)
    assert check.main() == 0 and calls[0]['challenge_profile'] == 'choices-overlay-to-kiosk'
    assert calls[0]['assets'] == named_input(vm_source=True, fixture_source=True)
    assert ChoicesOverlayToKioskQualification.journey(SimpleNamespace(), Mock()).plan is TRANSFER_PLAN
    # Planning must not allocate an empty real named bundle that the next
    # installed attempt would mistake for already prepared inputs.
    output = tmp_path / 'planned-input'
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', allocate)
    command = test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_choices_overlay_to_kiosk'])
    assert 'vm_artifacts.py' in str(command)
    allocate.assert_called_once_with(str(calls[0]['assets']))
    assert not output.exists()


@pytest.mark.parametrize('fault', ['', 'missing', 'replay', 'child', 'soft', 'approver', 'duration', 'source-mutated'])
@pytest.mark.parametrize('remembered', [False, True])
def test_transfer_real_step_immutable_comparison_before_reply(tmp_path, fault, remembered):
    binding = 'remembered' if remembered else 'transfer'
    plan = JourneyPlan('renamed-transfer', 'renamed-transfer', {
        'capture': f'ui:{binding}-overlay-jordan-read', 'destination': f'ui:{binding}-kiosk-jordan-read'}, {},
        request_transfer_checks={'destination': 'capture'})
    journey = ChoicesOverlayToKioskJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    source = transfer_request(jordan=True, remembered=remembered)
    if fault != 'missing': journey.check_transferred_request('capture', {'ui': {'request': source}})
    if fault == 'source-mutated': source['allow_soft'] = not source['allow_soft']
    value = transfer_request(overlay=False, jordan=True, remembered=remembered)
    if fault in ('child', 'soft', 'approver', 'duration'):
        key, replacement = {'child': ('child', 'fixture-child'), 'soft': ('allow_soft', not value['allow_soft']),
            'approver': ('approver', 'other-fixture-parent' if remembered else 'fixture-parent'),
            'duration': ('custom_text', '2.5' if remembered else '1.25')}[fault]
        value[key] = replacement
    if fault == 'replay': journey.check_transferred_request('destination', {'ui': {'request': value}})
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}, {'stage': 'capture'}]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': f'{binding}-kiosk-jordan-read', 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'request': value}))
    (tmp_path / 'destination.request.json').write_text(json.dumps({'stage': 'destination', 'screenshot': None}))
    if fault not in ('', 'source-mutated'):
        with pytest.raises((EvidenceError, a.UiError)): journey.step(Mock())
        assert not (tmp_path / 'destination.reply.json').exists()
    else:
        journey.step(Mock())
        assert journey.steps[-1]['comparison']['shared_child_choices_local_approver'] is True


@pytest.mark.parametrize('case', [False, True])
def test_transfer_recorder_constructor(tmp_path, monkeypatch, case):
    import installed_journey
    plan = REMEMBERED_PLAN if case else TRANSFER_PLAN
    journey_type = KioskRequestJourney if case else ChoicesOverlayToKioskJourney
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(), guestfs=Mock(),
        commands=Mock(), verified=SimpleNamespace(inputs={}))
    def worker(**kw):
        assert kw['guarded_observe'].__self__.plan is plan
        return {'shutdown_verified': True, 'worker_stopped': True, 'callback_closed': True, 'outcome': 'passed'}
    context.run_worker = worker
    monkeypatch.setattr(journey_type, 'validate', lambda self: [])
    installed_journey.record_installed_journey(MagicMock(), context, plan, journey_type=journey_type)


@pytest.mark.parametrize('jordan', [False, True])
@pytest.mark.parametrize('remembered', [False, True])
def test_transfer_actual_form_reader_decoder_and_child_uid(monkeypatch, capsys, jordan, remembered):
    ui, _, child, _, custom = overlay(monkeypatch)
    name = 'jordan' if jordan else 'riley'
    uid = 1002 if jordan else 1001
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda account: SimpleNamespace(pw_uid=
        1002 if account == 'onpc-child-jordan' else 1001))
    monkeypatch.setattr(a.os, 'getuid', lambda: uid)
    monkeypatch.setattr(a.os, 'geteuid', lambda: uid)
    child.value = str(uid)
    child.description = f'Selected account: {a.EXISTING_CHILD if jordan else a.CHILD}.'
    child.children[0].identity = 'kiosk-child-selected-' + str(uid)
    short = jordan if remembered else not jordan
    custom.value = '1.25' if short else '2.5'
    ui.find_id('kiosk-duration-custom').action.do_action(0)
    if short: ui.find_id('kiosk-soft-apps-toggle').states.add('checked')
    if remembered:
        ui.find_id('kiosk-approver-selector').setValue(str(ui.fixture_uids[a.OTHER_PARENT]))
        child.states.discard('sensitive')
    unit = Node(identity='kiosk-custom-duration-units', value='minutes')
    unit.parent = custom.parent
    custom.parent.children.append(unit)
    binding = 'remembered' if remembered else 'transfer'
    operation = f'{binding}-overlay-{name}-read'
    value = ui.run(operation, '')
    raw = capsys.readouterr().out.encode() + (json.dumps(value) + '\n').encode()
    def call(*_args, on_output, **_kwargs):
        for offset in range(0, len(raw), 17): on_output(raw[offset:offset + 17])
        return raw
    observer = UiObservations(SimpleNamespace(call=call, commands=SimpleNamespace(progress=None)))
    expected = transfer_request(jordan=jordan, remembered=remembered)
    assert observer.observe(operation)['request'] == expected
    monkeypatch.setattr(a.os, 'getuid', lambda: 1001 if jordan else 1002)
    with pytest.raises(a.UiError, match='overlay-account'):
        ui.run(f'{binding}-overlay-{name}-custom', '')
    custom.setText.assert_not_called()
    ui.find_id('kiosk-request-submit').action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'wrong-child', 'wrong-owner', 'disabled', 'prompt', 'uncertain'])
@pytest.mark.parametrize('remembered', [False, True])
def test_transfer_jordan_text_uses_shared_input_guards(monkeypatch, fault, remembered):
    ui, application, child, _, custom = overlay(monkeypatch)
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda account: SimpleNamespace(pw_uid=
        1002 if account == 'onpc-child-jordan' else 1001))
    monkeypatch.setattr(a.os, 'getuid', lambda: 1002)
    monkeypatch.setattr(a.os, 'geteuid', lambda: 1002)
    child.value = '1002'
    child.children[0].identity = 'kiosk-child-selected-1002'
    ui.find_id('kiosk-duration-custom').action.do_action(0)
    if remembered:
        ui.find_id('kiosk-approver-selector').setValue(str(ui.fixture_uids[a.OTHER_PARENT]))
        child.states.discard('sensitive')
    operation = ('remembered' if remembered else 'transfer') + '-overlay-jordan-text'
    if fault == 'wrong-child': child.value = '1001'
    if fault == 'wrong-owner': application.identity = a.KIOSK_APPLICATION
    if fault == 'disabled': custom.states.discard('sensitive')
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='mate-polkit-agent')
    if fault == 'uncertain': custom.setText.side_effect = TimeoutError('uncertain')
    if fault:
        with pytest.raises((a.UiError, TimeoutError)): ui.run(operation, '')
    else:
        ui.run(operation, '')
    assert custom.setText.call_count == (0 if fault in ('wrong-child', 'wrong-owner', 'disabled', 'prompt') else 1)
    if custom.setText.call_count: custom.setText.assert_called_once_with('1.25' if remembered else '2.5')
    if fault == 'uncertain':
        with pytest.raises(a.UiError, match='uncertain-input'): ui.run(operation, '')
        custom.setText.assert_called_once()


def test_transfer_shared_fragment_independent_named_caller():
    from request_flow import overlay_to_kiosk
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
require onpc_request_flow;
my $journey = onpc_journey->new(prefix => 'another-caller', review => 0, exchange => sub {
    my ($stage) = @_; push @events, ['stage', $stage];
    return {observed => $stage, station_destination => 'default-request-form'} if $stage =~ /station-branch$/;
    return {observed => $stage, ui_focused => 1} if $stage =~ /list$/;
    return {observed => $stage};
});
my $source = $journey->seen('original');
onpc_request_flow::overlay_to_kiosk($journey, $source, 'original', 'renamed', 'jordan');
my $ok = eval { onpc_request_flow::overlay_to_kiosk($journey, $source, 'original', 'repeat', 'jordan'); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    result = json.loads(run_perl(program).stdout)
    assert not result['ok'] and 'stale-observation' in result['error']
    assert [row[1] for row in result['events'] if row[0] == 'stage'] == [
        'original', *overlay_to_kiosk('renamed', child='jordan')]


def test_remembered_station_seeds_local_approver_from_distinct_default(monkeypatch):
    ui, selector, _, _ = accounts_form('approver')
    child = ui.find_id('kiosk-child-selector')
    child.value = '1002'
    child.children[0].identity = 'kiosk-child-selected-1002'
    child.description = f'Selected account: {a.EXISTING_CHILD}.'
    selector.setValue(str(ui.fixture_uids[a.OTHER_PARENT]))
    selector.setValue.reset_mock()
    value = ui.run('remembered-kiosk-jordan-approver', '')
    selector.setValue.assert_called_once_with(str(ui.fixture_uids[a.PARENT]))
    request = RequestObservation.from_request(value['request'], operation='remembered-kiosk-jordan-approver')
    assert request.child == 'existing-fixture-child' and request.approver == 'fixture-parent'
    assert request.duration_seconds == 1800 and request.custom_text is None and request.allow_soft is False


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
    status = Node('Estimated remaining time: 45m', identity='kiosk-request-status')
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
                'Estimated remaining time: 16m 15s' if value == 'custom' else
                'Estimated remaining time: 20m')
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


@pytest.mark.parametrize('completion', ['resolved', 'pending', 'denied', 'malformed'])
def test_fraction_estimate_waits_for_value_without_replaying_input(monkeypatch, completion):
    ui, _, _, status, custom = overlay(monkeypatch)
    ui.run('overlay-valid-custom-open', '')
    status.name = 'Estimated remaining time: '
    now = [0.0]
    sleeps = []
    ui.timeout = .4

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds
        if completion != 'pending':
            status.name = {
                'resolved': 'Estimated remaining time: 16m 15s',
                'denied': 'Request denied',
                'malformed': 'Estimated remaining time: invalid',
            }[completion]

    monkeypatch.setattr(a, 'time', SimpleNamespace(
        monotonic=lambda: now[0], monotonic_ns=lambda: int(now[0] * 1e9), sleep=sleep))
    if completion == 'resolved':
        result = ui.run('overlay-valid-fraction-read', '')['valid_choice']
        assert result['request']['duration_seconds'] == 75
        assert result['request']['custom_text'] == '1.25'
        assert result['estimate'] == {
            'kind': 'fixed', 'text': '16m 15s', 'seconds': 975, 'precision_seconds': 1}
        assert not ui.input_uncertain
    else:
        code = ('ui:timeout:kiosk-estimate' if completion == 'pending' else
                'ui:kiosk-estimate:request-denied' if completion == 'denied' else 'ui:time-duration')
        with pytest.raises(a.UiError, match=code):
            ui.run('overlay-valid-fraction-read', '')
        assert ui.input_uncertain
    assert sleeps and now[0] <= ui.timeout
    ui.find_id('kiosk-duration-custom').action.do_action.assert_called_once()
    custom.setText.assert_not_called()
    ui.find_id('kiosk-request-submit').action.do_action.assert_not_called()


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
    ui.prepare_launch_desktop = Mock()
    submit = Mock(side_effect=TimeoutError() if fault == 'submission' else None)
    monkeypatch.setattr(a.subprocess, 'run', submit)
    if fault:
        with pytest.raises((a.UiError, TimeoutError)): ui.run('overlay-native-command-launch', '')
    else: ui.run('overlay-native-command-launch', '')
    assert submit.call_count == (0 if fault == 'wrong-account' else 1)
    assert ui.prepare_launch_desktop.call_count == (0 if fault == 'wrong-account' else 1)
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
    PLAN, CHOICES_PLAN, PROMPT_PLAN, APPROVED_PLAN, IMMEDIATE_PLAN, FLOW_REJECTION_PLAN, FLOW_CANCEL_PLAN,
    LICENSE_PLAN, BROWSER_LINKS_PLAN, INFORMATION_PLAN, ABOUT_CASE_PLAN)
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
    elif plan in (APPROVED_PLAN, IMMEDIATE_PLAN, FLOW_REJECTION_PLAN, FLOW_CANCEL_PLAN):
        binding = {APPROVED_PLAN.worker_mode: 'approval', IMMEDIATE_PLAN.worker_mode: 'approval-immediate',
                   FLOW_REJECTION_PLAN.worker_mode: 'flow-rejection', FLOW_CANCEL_PLAN.worker_mode: 'flow-cancel'}[plan.worker_mode]
        program = program.replace('onpc_request_flow::overlay_valid_choices(',
                                  'onpc_request_flow::overlay_prompt(').replace(
                                      '}, $declared, $challenges);', '}, $declared, $challenges, "' + binding + '");')
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
        assert sum(event[0] == 'password' for event in result['events']) == (
            4 if plan is FLOW_REJECTION_PLAN else 3 if plan in (APPROVED_PLAN, IMMEDIATE_PLAN, FLOW_CANCEL_PLAN) else 2)
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
