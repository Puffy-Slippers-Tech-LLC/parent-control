"""System session helpers preserve fixture identity and never navigate menus.

Parallelism review: process-local session/UI doubles, private pytest files and
bounded waited Perl children. No live VM, display, bus, shared cache or new owner;
the existing compatible unit classification continues to apply.
"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import session_control as control


from accessible_ui import OPERATIONS, UiError
from tests.support.accessible_ui import Node, ui_for
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.paths import ROOT
from tests.support.perl import run_perl


PACKAGE_FORMAT = control.package_format


def test_retained_declarations_are_independent_shared_fragments():
    from journey_blocks import retained_parent_entry, native_activity_resume, prefixed_stages
    from retained_entry import SCREENS
    from private_artifacts import EvidenceError
    for source in ('desktop', 'child-desktop', 'same-user'):
        expected = retained_parent_entry(source=source)
        retained_parent_entry(source=source).clear()
        assert retained_parent_entry(source=source) == expected
        assert prefixed_stages('unrelated-return', expected)['unrelated-return-parent-retained'] == 'ui:retained-parent-read'
    for prefix, child in (('riley-resume', 'child'), ('jordan-resume', 'other-child')):
        fragment = native_activity_resume(prefix, child=child)
        assert all(SCREENS[stage] == operation for stage, operation in fragment.items())
        assert list(fragment.values()) == list(native_activity_resume('independent', child=child).values())
    with pytest.raises(EvidenceError): retained_parent_entry(source='locked')
    with pytest.raises(EvidenceError): native_activity_resume('independent', child='parent')


@pytest.mark.parametrize('fault', ['', 'window', 'page', 'settings', 'missing', 'replay'])
def test_shared_retained_engine_renamed_capture_and_real_reply(tmp_path, fault):
    from installed_journey import JourneyPlan
    from journey_checks import RetainedDesktopJourney
    from private_artifacts import EvidenceError
    screens = {'original': 'ui:retained-parent-leave', 'later': 'ui:retained-parent-read'}
    plan = JourneyPlan(prefix='independent-retention', worker_mode='unused', screen_tags=screens,
                       phases={'ready': 'setup', 'setup-detached': 'setup', 'original': 'start', 'later': 'start'})
    value = {'window': {'binding': 'parent', 'pid': 100, 'endpoint': [':1.10', '/window'], 'available': True},
             'page': 'app-limits', 'settings': {'child': 'fixture-child', 'limit_enabled': True,
                                             'allowance': ['15 minutes']}}
    journey = RetainedDesktopJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
        parent_expected={'original': {key: value[key] for key in ('page', 'settings')}},
        parent_checks={'later': 'original'}, window_checks={}, session_checks={})
    if fault != 'missing': journey.check_settings('original', {'ui': {'retained_parent': value}})
    current = json.loads(json.dumps(value))
    # Mutating nested decoder and caller-oracle values cannot rewrite the capture.
    value['window']['endpoint'].clear()
    value['settings']['allowance'].clear()
    if fault == 'window': current['window']['endpoint'] = [':1.20', '/replacement']
    if fault == 'page': current['page'] = 'screen-limits'
    if fault == 'settings': current['settings']['allowance'] = ['30 minutes']
    if fault == 'replay': journey.check_settings('later', {'ui': {'retained_parent': current}})
    journey.steps = [{'stage': s} for s in plan.stages[:-1]]
    journey.boot = 'b' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'retained-parent-read', 'retained_parent': current}))
    (tmp_path / 'later.request.json').write_text(json.dumps({'stage': 'later', 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert journey.failed and not (tmp_path / 'later.reply.json').exists()
    else:
        journey.step(Mock())
        assert (tmp_path / 'later.reply.json').exists()
        assert journey.steps[-1]['comparison']['same_parent_window_child_page_settings']


@pytest.mark.parametrize('fault', ['', 'changed', 'missing', 'replay', 'wrong-operation', 'cross-account'])
def test_shared_retained_session_endpoints_are_explicit_and_immutable(tmp_path, fault):
    from installed_journey import JourneyPlan
    from journey_checks import RetainedDesktopJourney
    from private_artifacts import EvidenceError
    screens = {'parent': 'ui:retained-parent-leave', 'initial-session': 'system:child-entry-same',
               'returned-session': 'system:standard-entry-retained' if fault == 'cross-account'
                                   else 'system:child-entry-retained'}
    plan = JourneyPlan(prefix='independent-session', worker_mode='unused', screen_tags=screens,
                       phases={stage: 'start' for stage in ('ready', 'setup-detached', *screens)})
    options = dict(parent_expected={'parent': {}}, parent_checks={}, window_checks={},
                   session_checks={'returned-session': 'initial-session'})
    if fault == 'cross-account':
        with pytest.raises(EvidenceError): RetainedDesktopJourney(SimpleNamespace(), Mock(), plan, **options)
        return
    journey = RetainedDesktopJourney(SimpleNamespace(), Mock(), plan, **options)
    value = {'operation': 'child-entry-same', 'outcome': 'passed', 'session_sha256': 'a' * 64}
    if fault != 'missing': journey.check_settings('initial-session', {'system': value})
    value.update(operation='child-entry-retained', session_sha256='b' * 64 if fault == 'changed' else 'a' * 64)
    if fault == 'wrong-operation': value['operation'] = 'standard-entry-retained'
    if fault == 'replay': journey.check_settings('returned-session', {'system': value})
    observed = {'system': value}
    if fault:
        with pytest.raises(EvidenceError): journey.check_settings('returned-session', observed)
    else:
        journey.check_settings('returned-session', observed)
        assert observed['comparison']['same_retained_child_desktop']


@pytest.mark.parametrize('fault', ['', 'changed', 'missing', 'replay'])
def test_shared_retained_window_proof_has_its_own_capture_boundary(fault):
    from installed_journey import JourneyPlan
    from journey_checks import RetainedDesktopJourney
    from private_artifacts import EvidenceError
    screens = {'original': 'ui:retained-parent-leave', 'foreground': 'ui:switch-parent'}
    plan = JourneyPlan(prefix='independent-window', worker_mode='unused', screen_tags=screens,
                       phases={stage: 'start' for stage in ('ready', 'setup-detached', *screens)})
    value = {'window': {'binding': 'parent', 'pid': 100, 'endpoint': [':1.10', '/window'], 'available': True},
             'page': 'app-limits', 'settings': {'child': 'fixture-child', 'limit_enabled': True,
                                             'allowance': ['15 minutes']}}
    journey = RetainedDesktopJourney(SimpleNamespace(), Mock(), plan,
        parent_expected={'original': {key: value[key] for key in ('page', 'settings')}},
        parent_checks={}, window_checks={'foreground': 'original'}, session_checks={})
    if fault != 'missing': journey.check_settings('original', {'ui': {'retained_parent': value}})
    current = json.loads(json.dumps(value['window']))
    value['window']['endpoint'].clear()
    if fault == 'changed': current['pid'] += 1
    if fault == 'replay': journey.check_settings('foreground', {'ui': {'window': current}})
    if fault:
        with pytest.raises(EvidenceError): journey.check_settings('foreground', {'ui': {'window': current}})
    else:
        journey.check_settings('foreground', {'ui': {'window': current}})


@pytest.mark.parametrize('checks', [{'later': 'later'}, {'original': 'later'}, {'later': 'absent'}])
def test_shared_retained_engine_refuses_missing_reversed_and_overlapping_endpoints(checks):
    from installed_journey import JourneyPlan
    from journey_checks import RetainedDesktopJourney
    from private_artifacts import EvidenceError
    screens = {'original': 'ui:retained-parent-leave', 'later': 'ui:retained-parent-read'}
    plan = JourneyPlan(prefix='invalid-retention', worker_mode='unused', screen_tags=screens,
                       phases={stage: 'start' for stage in ('ready', 'setup-detached', *screens)})
    with pytest.raises(EvidenceError):
        RetainedDesktopJourney(SimpleNamespace(), Mock(), plan,
            parent_expected={'original': {}}, parent_checks=checks, window_checks={}, session_checks={})


def retained_parent_probe():
    from retained_parent import PLAN
    program, binding = unlock_probe(PLAN)
    program = program.replace('onpc_desktop_session::qualify_retained_unlock',
                              'onpc_desktop_session::qualify_retained_parent')
    program = program.replace('$plan->{retained}, $plan->{invocations}', '$plan->{invocations}')
    return program, binding


def retained_entry_probe():
    from retained_entry import PLAN
    program, binding = unlock_probe(PLAN)
    program = program.replace('onpc_desktop_session::qualify_retained_unlock',
                              'onpc_desktop_session::qualify_retained_entry')
    program = program.replace('$plan->{retained}, $plan->{invocations}', '$plan->{invocations}')
    program = program.replace(r'\Alock-recipient-', r'\Ariley-unlock-lock-recipient-')
    program = program.replace('return {observed => $stage};',
        "return {observed => $stage, gdm_return_state => 'account-list'} if $stage eq 'denied-return-state'; return {observed => $stage};")
    return program, binding


def test_retained_entry_actual_worker_order_and_every_refusal_stop():
    from retained_entry import PLAN
    program, binding = retained_entry_probe()
    result = json.loads(run_perl(program, '', binding).stdout)
    assert result['ok'], (result['error'], result['events'][-12:])
    events = result['events']
    assert [row[1] for row in events if row[0] == 'stage'] == list(PLAN.screen_tags)
    assert events.count(['secret']) == 9
    assert events.count(['key', 'spc']) == 2
    assert events.count(['key', 'alt-tab']) == 0
    assert events[-1] == ['power', 'off']
    for stage in PLAN.screen_tags:
        failure = json.loads(run_perl(program, stage, binding).stdout)
        assert not failure['ok'], failure
        assert failure['events'] == events[:events.index(['stage', stage]) + 1]
    assert all(tag[3:] in OPERATIONS if tag.startswith('ui:') else tag[7:] in control.BINDINGS
               for tag in PLAN.screen_tags.values())


def test_retained_entry_recorder_startup_and_actual_worker_titles(tmp_path):
    from unittest.mock import MagicMock
    from installed_journey import record_installed_journey, matched_screens
    from private_artifacts import EvidenceError
    from retained_entry import PLAN, RetainedEntryJourney
    program, binding = retained_entry_probe()
    program = program.replace('sub record_info { }',
                              "sub record_info { push @main::events, ['title', $_[0]]; }")
    events = json.loads(run_perl(program, '', binding).stdout)['events']
    titles = [{'title': row[1], 'result': 'ok'} for row in events if row[0] == 'title']
    observations = [{'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
        'operation': tag.split(':', 1)[1], 'outcome': 'passed'},
        **({'challenge': PLAN.challenge_at(stage)} if PLAN.challenge_at(stage) else {})}
        for stage, tag in PLAN.screen_tags.items()]
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': titles}))
    assert [item['stage'] for item in matched_screens(tmp_path, PLAN, observations)] == list(PLAN.screen_tags)
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    context.recorder = MagicMock(assertion=Mock())
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is RetainedEntryJourney and journey.plan is PLAN
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(context.recorder, context, PLAN, journey_type=RetainedEntryJourney)
    context.run_worker.assert_called_once()


@pytest.mark.parametrize('role', ['child', 'standard'])
@pytest.mark.parametrize('fault', ['', 'replaced', 'missing'])
def test_retained_entry_real_step_refuses_replaced_child_before_reply(tmp_path, role, fault):
    from retained_entry import PLAN, RetainedEntryJourney
    from private_artifacts import EvidenceError
    prefix = 'riley' if role == 'child' else 'jordan'
    journey = RetainedEntryJourney(SimpleNamespace(directory=tmp_path), Mock())
    value = {'operation': role + '-entry-same', 'outcome': 'passed', 'entry': 'same',
             'session_sha256': 'a' * 64}
    if fault != 'missing':
        journey.check_settings(prefix + '-same-entry-guard', {'system': value})
    value['session_sha256'] = 'b' * 64 if fault == 'replaced' else 'a' * 64
    stage = prefix + '-return-identity'
    journey.steps = [{'stage': s} for s in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
    journey.transport = Mock()
    from unittest.mock import patch
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    with patch('installed_journey.session_control.observe', return_value=value):
        if fault:
            with pytest.raises(EvidenceError): journey.step(Mock())
            assert journey.failed and not (tmp_path / (stage + '.reply.json')).exists()
        else:
            journey.step(Mock())
            assert (tmp_path / (stage + '.reply.json')).exists()
            assert journey.steps[-1]['comparison']['same_retained_child_desktop']


@pytest.mark.parametrize('role', ['parent', 'child', 'standard'])
@pytest.mark.parametrize('mode', ['fresh', 'retained', 'same', 'lock', 'refusals'])
def test_explicit_entry_guard_and_decoder_are_read_only(monkeypatch, role, mode):
    greeter = {'g': props('42', kind='greeter')}
    current = greeter if mode == 'fresh' else (
        {**greeter, '7': props(active='no', locked='yes')} if mode == 'retained' else
        {'7': props(locked='yes' if mode == 'lock' else 'no')})
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000))
    monkeypatch.setattr(control, 'sessions', Mock(return_value=current))
    submit = Mock()
    monkeypatch.setattr(control, 'submit', submit)
    result = control.execute(role + '-entry-' + mode)
    assert result['entry'] == mode
    assert (result['session_sha256'] is None) == (mode == 'fresh')
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    assert control.observe(transport, role + '-entry-' + mode) == result
    submit.assert_not_called()


@pytest.mark.parametrize('mode', ['fresh', 'retained', 'same', 'lock'])
@pytest.mark.parametrize('fault', ['wrong-state', 'wrong-owner', 'ambiguous', 'changed'])
def test_explicit_entry_guard_refuses_wrong_state_without_input(monkeypatch, mode, fault):
    current = {'g': props('42', kind='greeter')}
    if mode == 'retained': current['7'] = props(active='no', locked='yes')
    if mode in ('same', 'lock'): current = {'7': props(locked='yes' if mode == 'lock' else 'no')}
    if fault == 'wrong-state':
        current = {'7': props()} if mode in ('fresh', 'retained', 'lock') else {'g': props('42', kind='greeter')}
    elif fault == 'wrong-owner':
        if mode == 'fresh': current['7'] = props(active='no', locked='yes')
        else: current['7']['User'] = '1001'
    elif fault == 'ambiguous': current['8'] = props()
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000))
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[current, {}] if fault == 'changed' else [current]))
    submit = Mock()
    monkeypatch.setattr(control, 'submit', submit)
    with pytest.raises(control.SessionError): control.execute('child-entry-' + mode)
    submit.assert_not_called()


def test_retained_entry_registration_uses_maintained_vm_fixture_inputs(monkeypatch):
    import check_e2e_retained_entry as check
    from retained_entry import PLAN
    from parent_setup_qualification import RetainedEntryQualification
    from tools import test_commands
    context = SimpleNamespace()
    assert RetainedEntryQualification.journey(context, Mock()).plan is PLAN
    smoke = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 0 and smoke.call_args.kwargs['parent_entry'] == 'retained-children'
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', Mock(return_value='prepared'))
    command = test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_retained_entry'])
    assert any(value.endswith('/vm_artifacts.py') for value in command)


@pytest.mark.parametrize('fault', ['other-child-receipt', 'lock-ack', 'lock-identity'])
def test_retained_entry_mismatched_receipts_release_no_secret_or_later_input(fault):
    program, binding = retained_entry_probe()
    if fault == 'other-child-receipt':
        program = program.replace("return {observed => $stage, challenge => {id => $id, role => $role,",
            "return {observed => $stage, challenge => {id => $id, role => $stage eq 'jordan-fresh-standard-recipient-rechecked' ? 'child' : $role,")
        boundary = 'jordan-fresh-standard-recipient-rechecked'
    else:
        boundary = 'riley-unlock-lock-recipient-rechecked'
        if fault == 'lock-ack':
            program = program.replace("return {observed => $stage, lock_recipient =>",
                "return {observed => $stage eq 'riley-unlock-lock-recipient-rechecked' ? 'lock-recipient-rechecked' : $stage, lock_recipient =>")
        else:
            program = program.replace("challenge_id => 'a' x 64", "challenge_id => scalar(($stage eq 'riley-unlock-lock-recipient-rechecked' ? 'b' : 'a') x 64)")
    result = json.loads(run_perl(program, '', binding).stdout)
    assert not result['ok'] and result['events'][-1] == ['stage', boundary]


@pytest.mark.parametrize('binding', [
    ('child', 'gdm', 'same', 'success', None),
    ('child', 'desktop', 'fresh', 'success', None),
    ('child', 'desktop', 'retained', 'success', 'child'),
    ('child', 'locked', 'same', 'success', None),
    ('other-child', 'locked', 'lock', 'success', None),
    ('other-child', 'gdm', 'fresh', 'time-denied', None),
])
def test_desktop_entry_rejects_incompatible_declared_modes_before_observation(binding):
    from journey_blocks import desktop_entry
    from private_artifacts import EvidenceError
    account, source, mode, expected, source_account = binding
    with pytest.raises(EvidenceError):
        desktop_entry(account, source=source, entry=mode, expected=expected, source_account=source_account)
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $binding = decode_json($ARGV[1]);
my $journey = onpc_journey->new(exchange => sub { push @events, ['input']; die 'unexpected'; },
    prefix => 'independent-entry', review => 0);
my $ok = eval { onpc_desktop_session::enter_desktop($journey, $binding->[1], $binding->[0],
    $binding->[2], $binding->[3], 'independent', $binding->[4]); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
    result = json.loads(run_perl(program, '', json.dumps(binding)).stdout)
    assert not result['ok'] and result['events'] == []


def test_retained_parent_actual_worker_order_and_every_refusal_stop():
    from retained_parent import PLAN
    program, binding = retained_parent_probe()
    result = json.loads(run_perl(program, '', binding).stdout)
    assert result['ok'], result
    events = result['events']
    assert [row[1] for row in events if row[0] == 'stage'] == list(PLAN.screen_tags)
    assert events.count(['secret']) == 5
    assert events.count(['key', 'alt-tab']) == 0
    assert events[-1] == ['power', 'off']
    # Every refusal must stop before any later command, password or reply.
    for stage in PLAN.screen_tags:
        failure = json.loads(run_perl(program, stage, binding).stdout)
        assert not failure['ok'], failure
        assert failure['events'] == events[:events.index(['stage', stage]) + 1]
    assert all(tag[3:] in OPERATIONS if tag.startswith('ui:') else tag[7:] in control.BINDINGS
               for tag in PLAN.screen_tags.values())


def test_retained_parent_recorder_startup_and_actual_worker_titles(tmp_path):
    from unittest.mock import MagicMock
    from installed_journey import record_installed_journey, matched_screens
    from private_artifacts import EvidenceError
    from retained_parent import PLAN, RetainedParentJourney
    program, binding = retained_parent_probe()
    program = program.replace('sub record_info { }',
                              "sub record_info { push @main::events, ['title', $_[0]]; }")
    events = json.loads(run_perl(program, '', binding).stdout)['events']
    titles = [{'title': row[1], 'result': 'ok'} for row in events if row[0] == 'title']
    observations = []
    for stage, tag in PLAN.screen_tags.items():
        item = {'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
            'operation': tag.split(':', 1)[1], 'outcome': 'passed'}}
        if PLAN.challenge_at(stage): item['challenge'] = PLAN.challenge_at(stage)
        observations.append(item)
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': titles}))
    assert [item['stage'] for item in matched_screens(tmp_path, PLAN, observations)] == list(PLAN.screen_tags)
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    context.recorder = MagicMock(assertion=Mock())
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is RetainedParentJourney and journey.plan is PLAN
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(context.recorder, context, PLAN, journey_type=RetainedParentJourney)
    context.run_worker.assert_called_once()


@pytest.mark.parametrize('fault', ['', 'window', 'child', 'page', 'settings', 'missing'])
def test_retained_parent_real_step_compares_immutable_entry_before_reply(tmp_path, fault):
    from retained_parent import PLAN, RetainedParentJourney
    from private_artifacts import EvidenceError
    value = {'window': {'binding': 'parent', 'pid': 100, 'endpoint': [':1.10', '/window'],
                        'available': True}, 'page': 'app-limits',
             'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['15 minutes']}}
    journey = RetainedParentJourney(SimpleNamespace(directory=tmp_path), Mock())
    if fault != 'missing': journey.check_settings('before', {'ui': {'retained_parent': value}})
    current = json.loads(json.dumps(value))
    value['settings']['allowance'].clear()
    if fault == 'window': current['window']['pid'] += 1
    if fault == 'child': current['settings']['child'] = 'existing-fixture-child'
    if fault == 'page': current['page'] = 'screen-limits'
    if fault == 'settings': current['settings']['allowance'] = ['30 minutes']
    stage = 'return-parent-retained'
    journey.steps = [{'stage': s} for s in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'retained-parent-read', 'retained_parent': current}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert journey.failed and not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['comparison']['same_parent_window_child_page_settings']


@pytest.mark.parametrize('fault', ['', 'locked', 'wrong-owner', 'replacement'])
def test_parent_desktop_identity_is_read_only_and_refuses_wrong_entry(monkeypatch, fault):
    current = {'7': props(locked='yes' if fault == 'locked' else 'no')}
    if fault == 'wrong-owner': current['7']['User'] = '1001'
    account = SimpleNamespace(pw_uid=1000)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[current,
        {'8': props()} if fault == 'replacement' else current]))
    submit = Mock()
    monkeypatch.setattr(control, 'submit', submit)
    if fault:
        with pytest.raises(control.SessionError): control.execute('parent-desktop-identity')
    else:
        result = control.execute('parent-desktop-identity')
        assert result['unlocked'] is True and len(result['session_sha256']) == 64
        transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
        assert control.observe(transport, 'parent-desktop-identity') == result
    submit.assert_not_called()


@pytest.mark.parametrize('operation', ['retained-parent-read', 'retained-parent-leave'])
@pytest.mark.parametrize('fault', ['', 'child', 'replaced', 'absent'])
def test_retained_parent_adapter_never_repairs_selection_and_reads_screen_limits(operation, fault):
    from accessible_ui import AccessibleUI, CHILD, CHILD_IDENTITIES
    ui = AccessibleUI.__new__(AccessibleUI)
    window = {'binding': 'parent', 'pid': 100, 'endpoint': [':1.10', '/window'], 'available': True}
    ui.desktop_result = Mock()
    ui.window_switch_proof = Mock(side_effect=UiError('ui:switch-absent') if fault == 'absent'
        else [window, {**window, 'pid': 101} if fault == 'replaced' else window])
    ui.parent_initial_selection = Mock(return_value='existing-fixture-child' if fault == 'child'
                                       else CHILD_IDENTITIES[CHILD])
    ui.get_value = Mock(return_value='app-limits')
    ui.set_value = Mock()
    ui.parent_page = Mock(return_value={'child': 'fixture-child', 'limit_enabled': True,
                                      'allowance': ['15 minutes']})
    if fault:
        with pytest.raises(UiError): ui.retained_parent_operation(operation)
    else:
        result = ui.retained_parent_operation(operation)['retained_parent']
        assert result['page'] == 'app-limits' and result['window'] == window
        ui.parent_page.assert_called_once_with(CHILD, 'Screen Limits')
        if operation.endswith('leave'): ui.set_value.assert_called_once_with('parent-pages', 'app-limits')
        else: ui.set_value.assert_not_called()
    if fault in ('child', 'absent'):
        ui.parent_page.assert_not_called()
        ui.set_value.assert_not_called()


def test_retained_parent_absence_refuses_without_launch():
    from accessible_ui import AccessibleUI
    ui = AccessibleUI.__new__(AccessibleUI)
    ui.desktop_result = Mock()
    ui.parent_search_closed = Mock(return_value=True)
    ui.wait = Mock(side_effect=lambda predicate, *args, **kwargs: predicate())
    ui.existing_window = Mock(side_effect=UiError('ui:switch-absent'))
    ui.parent_command_launch = Mock()
    assert ui.retained_parent_operation('retained-parent-absent-refused') == {'refused': True}
    assert ui.parent_search_closed.call_count == 2
    ui.parent_command_launch.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'pid', 'endpoint', 'page', 'settings', 'extra', 'missing'])
def test_retained_parent_controller_decodes_public_proof_and_refuses_malformed_reply(fault):
    from ui_observations import UiObservations
    from private_artifacts import EvidenceError
    value = {'window': {'binding': 'parent', 'pid': 100, 'endpoint': [':1.10', '/window'],
                        'available': True}, 'page': 'app-limits',
             'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['15 minutes']}}
    result = {'operation': 'retained-parent-read', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider', 'retained_parent': value}
    if fault == 'pid': value['window']['pid'] = True
    if fault == 'endpoint': value['window']['endpoint'][0] = 'foreign'
    if fault == 'page': value['page'] = 'foreign'
    if fault == 'settings': value['settings']['allowance'] = ['private text']
    if fault == 'extra': result['extra'] = True
    if fault == 'missing': value.pop('window')
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(return_value=(json.dumps(result).encode(), []))
    if fault:
        with pytest.raises(EvidenceError): reader.observe('retained-parent-read')
    else:
        assert reader.observe('retained-parent-read')['retained_parent'] == value


def test_retained_parent_registration_uses_maintained_vm_inputs(monkeypatch):
    import check_e2e_retained_parent as check
    from retained_parent import PLAN
    from parent_setup_qualification import RetainedParentQualification
    from tools import test_commands
    context = SimpleNamespace()
    assert RetainedParentQualification.journey(context, Mock()).plan is PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    smoke = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 0 and smoke.call_args.kwargs['parent_entry'] == 'retained'
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', Mock(return_value='prepared'))
    command = test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_retained_parent'])
    assert any(value.endswith('/vm_artifacts.py') for value in command)


@pytest.mark.parametrize('selector,mode', [
    ('check_e2e_window_switch', 'window_switch'),
    ('check_e2e_set_an_allowance_for_a_named_child', 'set_allowance'),
])
def test_retained_parent_regressions_consume_selected_vm_packages(monkeypatch, selector, mode):
    import importlib
    check = importlib.import_module(selector)
    inputs = Mock(return_value='selected-vm-inputs')
    smoke = Mock(return_value=0)
    monkeypatch.setattr(check, 'named_input', inputs)
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 0
    inputs.assert_called_once_with(vm_source=True)
    assert smoke.call_args.kwargs['assets'] == 'selected-vm-inputs'
    assert smoke.call_args.kwargs[mode] is True


@pytest.fixture(autouse=True)
def platform(monkeypatch):
    monkeypatch.setattr(control, 'package_format', lambda: 'deb')


@pytest.mark.parametrize('release,expected', [
    ('ID=ubuntu\nVERSION_ID="26.04"\n', 'deb'),
    ('ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n', 'rpm'),
    ('ID=fedora\nVERSION_ID=44\nVARIANT_ID=server\n', None),
    ('ID=fedora\nVERSION_ID=43\nVARIANT_ID=workstation\n', None),
    ('ID=ubuntu\nVERSION_ID=24.04\n', None),
])
def test_package_platform_comes_from_supported_os_release(monkeypatch, release, expected):
    monkeypatch.setattr(control, 'Path', lambda name: SimpleNamespace(read_text=lambda: release))
    if expected:
        assert PACKAGE_FORMAT() == expected
    else:
        with pytest.raises(control.SessionError, match='package-platform'):
            PACKAGE_FORMAT()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('name,rpm_name', [('gdm3', 'gdm'), ('gnome-shell', 'gnome-shell'),
    ('mate-polkit', 'mate-polkit'), ('libgtk-4-1', 'gtk4'), ('gcr', 'gcr4')])
@pytest.mark.parametrize('fault', [False, True])
def test_provider_metadata_queries_correct_package_and_bounds_reply(
        monkeypatch, package_format, name, rpm_name, fault):
    monkeypatch.setattr(control, 'package_format', lambda: package_format)
    query = Mock(return_value='private text\nother' if fault else '0:50.1-1.fc44\n')
    monkeypatch.setattr(control.subprocess, 'check_output', query)
    if fault:
        with pytest.raises(control.SessionError, match='package-version'):
            control.installed_package_version(name)
    else:
        assert control.installed_package_version(name) == '0:50.1-1.fc44'
    assert query.call_args.kwargs == {'text': True, 'timeout': 5}
    assert query.call_args.args[0] == (['/usr/bin/rpm', '-q', '--queryformat',
        '%{EPOCHNUM}:%{VERSION}-%{RELEASE}', rpm_name] if package_format == 'rpm' else
        ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', name])


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_platform_package_path_and_administrator_group(monkeypatch, package_format):
    monkeypatch.setattr(control, 'package_format', lambda: package_format)
    assert control.administrator_group() == ('wheel' if package_format == 'rpm' else 'sudo')
    for binding in ('previous', 'current'):
        assert str(control.package_path(binding)) == '/var/lib/onpc-e2e-assets/' + (
            'previous/' if binding == 'previous' else '') + 'package.' + package_format


def test_session_readback_does_not_combine_both_sides_of_a_seat_switch(monkeypatch):
    # The source is read before the switch, then GDM after it. There was never
    # more than one active session, but the first sequential scan says otherwise.
    source = props(locked='yes')
    greeter = props('120', active='no', kind='greeter')
    reads = []

    def call(argv):
        if argv[1] == 'list-sessions':
            return '7 1000\n8 120\n'
        identity = argv[2]
        reads.append(identity)
        value = dict(source if identity == '7' else greeter)
        if len(reads) == 1:
            source['Active'] = 'no'
            greeter['Active'] = 'yes'
        return '\n'.join(f'{key}={item}' for key, item in value.items())

    monkeypatch.setattr(control, 'call', call)
    current = control.sessions()
    assert reads == ['7', '8'] * 3
    assert current == {'7': source, '8': greeter}
    assert control.destination(current, '7', 1000, 'switch-user')


def test_stable_multiple_active_sessions_still_refuse(monkeypatch):
    current = {'7': props(locked='yes'), '8': props('120', kind='greeter')}
    scan = Mock(return_value=current)
    monkeypatch.setattr(control, 'session_scan', scan)
    with pytest.raises(control.SessionError, match='ambiguous-destination'):
        control.destination(control.sessions(), '7', 1000, 'switch-user')
    assert scan.call_count == 2


def test_continuously_changing_sessions_refuse_with_bounded_reads(monkeypatch):
    scan = Mock(side_effect=[{'7': props(locked=value)}
                             for value in ('no', 'yes', 'no', 'yes')])
    monkeypatch.setattr(control, 'session_scan', scan)
    with pytest.raises(control.SessionError, match='unstable-observation'):
        control.sessions()
    assert scan.call_count == 4


def test_stabilized_wrong_source_owner_still_refuses(monkeypatch):
    switched = {'7': props('1001', active='no', locked='yes'),
                '8': props('120', kind='greeter')}
    monkeypatch.setattr(control, 'session_scan', Mock(side_effect=[
        {'7': props()}, switched, switched]))
    with pytest.raises(control.SessionError, match='source-replaced'):
        control.destination(control.sessions(), '7', 1000, 'switch-user')


def test_session_scan_errors_are_not_retried_as_transitions(monkeypatch):
    scan = Mock(side_effect=control.SessionError('session:session-properties'))
    monkeypatch.setattr(control, 'session_scan', scan)
    with pytest.raises(control.SessionError, match='session-properties'):
        control.sessions()
    scan.assert_called_once_with()


@pytest.mark.parametrize('fault', ['wrong-owner', 'remote', 'wrong-seat', 'greeter',
                                   'wrong-lock-state', 'multiple-active', 'multiple-owned', 'missing'])
@pytest.mark.parametrize('locked', [False, True])
def test_source_refuses_wrong_or_ambiguous_sessions(fault, locked):
    source = props(locked='yes' if locked else 'no')
    current = {'7': source}
    if fault == 'wrong-owner':
        source['User'] = '1001'
    elif fault == 'remote':
        source['Remote'] = 'yes'
    elif fault == 'wrong-seat':
        source['Seat'] = 'seat1'
    elif fault == 'greeter':
        source['Class'] = 'greeter'
    elif fault == 'wrong-lock-state':
        source['LockedHint'] = 'no' if locked else 'yes'
    elif fault == 'multiple-active':
        current['8'] = props('1001')
    elif fault == 'multiple-owned':
        current['8'] = props(active='no')
    else:
        current.clear()
    with pytest.raises(control.SessionError):
        control.source_session(current, 1000, locked=locked)


def test_source_and_independent_results_distinguish_logout_lock_and_switch():
    assert control.source_session({'7': props()}, 1000) == '7'
    assert control.source_session({'7': props(locked='yes')}, 1000, locked=True) == '7'
    greeter = props('120', kind='greeter')
    switched = {'7': props(active='no', locked='yes'), '8': greeter}
    assert control.destination(switched, '7', 1000, 'switch-user')
    assert control.destination(switched, '7', 1000, 'return-greeter')
    assert not control.destination({'7': props(locked='yes')}, '7', 1000, 'return-greeter')
    assert not control.destination({'7': props(active='no'), '8': greeter},
                                   '7', 1000, 'return-greeter')
    assert not control.destination(switched, '7', 1000, 'logout')
    assert control.destination({'8': greeter}, '7', 1000, 'logout')
    assert not control.destination({'7': props()}, '7', 1000, 'lock')
    assert control.destination({'7': props(locked='yes')}, '7', 1000, 'lock')
    for action in ('switch-user', 'return-greeter'):
        with pytest.raises(control.SessionError, match='source-lost'):
            control.destination({'8': greeter}, '7', 1000, action)
        with pytest.raises(control.SessionError, match='source-replaced'):
            control.destination({'7': props('1001'), '8': greeter}, '7', 1000, action)


def test_logout_is_one_direct_command_without_force_or_a_shell(monkeypatch):
    call = Mock()
    monkeypatch.setattr(control, 'call', call)
    control.submit('logout')
    call.assert_called_once_with(['/usr/bin/gnome-session-quit', '--logout', '--no-prompt'])
    call.reset_mock()
    call.side_effect = TimeoutError
    with pytest.raises(TimeoutError):
        control.submit('logout')
    assert call.call_count == 1


@pytest.mark.parametrize('active,locked', [('yes', 'no'), ('no', 'yes')])
def test_root_maintenance_logout_retains_other_desktops(monkeypatch, active, locked):
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture')
    source = props(active=active, locked=locked)
    other = props('1001', active='no' if active == 'yes' else 'yes')
    before = {'7': source, '8': other}
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwuid', lambda _: account)
    monkeypatch.setattr(control.os, 'getgrouplist', lambda *_: [1000])
    monkeypatch.setattr(control, 'environment', lambda _: {'bound': 'desktop'})
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[before, before, {'8': other}]))
    run = Mock()
    monkeypatch.setattr(control.subprocess, 'run', run)
    assert control.maintenance_logout(1000, '7') == {
        'operation': 'maintenance-logout', 'outcome': 'passed',
        'source_retained': False, 'other_desktops_retained': True}
    assert run.call_count == 1
    assert run.call_args.args[0] == control.LOGOUT_COMMAND
    assert run.call_args.kwargs['user'] == 1000
    assert run.call_args.kwargs['env'] == {'bound': 'desktop'}
    assert control.os.geteuid() == 0


@pytest.mark.parametrize('fault', ['nonroot', 'owner', 'ambiguous', 'changed', 'uncertain', 'other-lost'])
def test_root_maintenance_logout_refuses_without_fallback(monkeypatch, fault):
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture')
    before = {'7': props(active='no', locked='yes'), '8': props('1001')}
    after = {'8': props('1001')}
    if fault == 'owner':
        before['7']['User'] = '1002'
    if fault == 'ambiguous':
        before['9'] = props(active='no')
    monkeypatch.setattr(control.os, 'geteuid', lambda: 1 if fault == 'nonroot' else 0)
    monkeypatch.setattr(control.pwd, 'getpwuid', lambda _: account)
    monkeypatch.setattr(control.os, 'getgrouplist', lambda *_: [1000])
    monkeypatch.setattr(control, 'environment', lambda _: {})
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        before, after if fault == 'changed' else before,
        {} if fault == 'other-lost' else after]))
    run = Mock(side_effect=TimeoutError if fault == 'uncertain' else None)
    monkeypatch.setattr(control.subprocess, 'run', run)
    with pytest.raises((control.SessionError, TimeoutError)):
        control.maintenance_logout(1000, '7')
    assert run.call_count == (1 if fault in ('uncertain', 'other-lost') else 0)


@pytest.mark.parametrize('action', ['switch-user', 'return-greeter'])
def test_greeter_command_locks_only_an_unlocked_source_and_never_retries(monkeypatch, action):
    events = []
    gdm = SimpleNamespace(goto_login_session_sync=Mock())
    monkeypatch.setitem(__import__('sys').modules, 'gi', SimpleNamespace(require_version=Mock()))
    monkeypatch.setitem(__import__('sys').modules, 'gi.repository', SimpleNamespace(Gdm=gdm))
    monkeypatch.setattr(control, 'call', lambda argv: events.append(argv))
    control.submit(action)
    if action == 'switch-user':
        assert events[0] == [
            '/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
            '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.Lock']
    assert len(events) == (2 if action == 'switch-user' else 1)
    assert events[-1][:8] == [
        '/usr/bin/systemd-run', '--user', '--quiet', '--collect', '--wait',
        '--pipe', '--service-type=exec', '/usr/bin/python3']
    assert events[-1][8:10] == ['-I', '-c']
    assert 'Gdm.goto_login_session_sync(None)' in events[-1][-1]
    gdm.goto_login_session_sync.assert_not_called()
    events.clear()
    def fail(_):
        events.append('failed-command')
        raise TimeoutError
    monkeypatch.setattr(control, 'call', fail)
    with pytest.raises(TimeoutError):
        control.submit(action)
    assert events == ['failed-command']


@pytest.mark.parametrize('binding', ['root-logout', 'parent-reboot', 'parent-logout;id',
                                    'standard-continuous-activity', ''])
def test_unregistered_commands_refuse_before_session_lookup(monkeypatch, binding):
    read = Mock()
    monkeypatch.setattr(control, 'sessions', read)
    with pytest.raises(control.SessionError, match='binding'):
        control.execute(binding)
    read.assert_not_called()


@pytest.mark.parametrize('fault', ['initial-owner', 'changed-source', 'initial-lock', 'changed-lock'])
@pytest.mark.parametrize('binding', ['parent-switch-user', 'parent-logout',
                                    'standard-return-greeter', 'parent-continuous-activity',
                                    'child-switch-user'])
def test_execute_checks_ownership_and_lock_state_again_after_dropping_privileges(
        monkeypatch, fault, binding):
    role, action = control.BINDINGS[binding]
    locked = 'yes' if action == 'return-greeter' else 'no'
    wrong_lock = 'no' if locked == 'yes' else 'yes'
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name=control.ACCOUNTS[role])
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(control, 'environment', lambda _: {})
    monkeypatch.setattr(control.os, 'environ', {})
    for name in ('initgroups', 'setgid', 'setuid'):
        monkeypatch.setattr(control.os, name, Mock())
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        {'7': props('1001' if fault == 'initial-owner' else '1000',
                    locked=wrong_lock if fault == 'initial-lock' else locked)},
        {'8' if fault == 'changed-source' else '7':
            props(locked=wrong_lock if fault == 'changed-lock' else locked)},
    ]))
    submit = Mock()
    monkeypatch.setattr(control, 'submit', submit)
    prepare = Mock()
    monkeypatch.setattr(control, 'prepare_continuous_activity', prepare)
    with pytest.raises(control.SessionError):
        control.execute(binding)
    submit.assert_not_called()
    prepare.assert_not_called()


def test_child_switch_binds_riley_and_observes_the_retained_locked_session(monkeypatch):
    account = SimpleNamespace(pw_uid=1001, pw_gid=1001, pw_name='onpc-child-riley')
    lookup = Mock(return_value=account)
    monkeypatch.setattr(control.pwd, 'getpwnam', lookup)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control, 'environment', lambda _: {'bound': 'child'})
    monkeypatch.setattr(control.os, 'environ', {})
    identity = {}
    for name in ('initgroups', 'setgid', 'setuid'):
        identity[name] = Mock()
        monkeypatch.setattr(control.os, name, identity[name])
    before = {'7': props('1001')}
    after = {'7': props('1001', active='no', locked='yes'),
             '8': props('120', kind='greeter')}
    scans = Mock(side_effect=[before, before, after])
    monkeypatch.setattr(control, 'sessions', scans)
    submit = Mock()
    monkeypatch.setattr(control, 'submit', submit)
    assert control.execute('child-switch-user') == {
        'operation': 'child-switch-user', 'outcome': 'passed', 'interface': 'system session',
        'source_retained': True, 'destination': 'greeter'}
    lookup.assert_called_once_with('onpc-child-riley')
    identity['initgroups'].assert_called_once_with('onpc-child-riley', 1001)
    identity['setgid'].assert_called_once_with(1001)
    identity['setuid'].assert_called_once_with(1001)
    assert control.os.environ == {'bound': 'child'}
    submit.assert_called_once_with('switch-user')
    assert scans.call_count == 3


def test_continuous_activity_only_verifies_baseline_and_reads_back(monkeypatch):
    call = Mock(side_effect=['uint32 0\n', 'uint32 0\n'])
    monkeypatch.setattr(control, 'call', call)
    assert control.prepare_continuous_activity() == 0
    assert [item.args[0] for item in call.call_args_list] == [
        ['/usr/bin/gsettings', 'get', 'org.gnome.desktop.session', 'idle-delay'],
        ['/usr/bin/gsettings', 'get', 'org.gnome.desktop.session', 'idle-delay'],
    ]


@pytest.mark.parametrize('responses,calls,exception', [
    (['300'], 1, control.SessionError),
    (['uint32 4294967296'], 1, control.SessionError),
    (['uint32 300'], 1, control.SessionError),
    (['uint32 4294967295'], 1, control.SessionError),
    (['uint32 0', TimeoutError()], 2, TimeoutError),
    (['uint32 0', 'uint32 300'], 2, control.SessionError),
])
def test_continuous_activity_refuses_bad_values_and_never_replays(monkeypatch, responses, calls, exception):
    command = Mock(side_effect=responses)
    monkeypatch.setattr(control, 'call', command)
    with pytest.raises(exception):
        control.prepare_continuous_activity()
    assert command.call_count == calls


@pytest.mark.parametrize('source_changed', [False, True])
def test_continuous_activity_belongs_to_the_bound_unprivileged_parent(monkeypatch, source_changed):
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name=control.ACCOUNTS['parent'])
    identity = [0]
    monkeypatch.setattr(control.os, 'geteuid', lambda: identity[0])
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(control, 'environment', lambda _: {'fixture': 'parent'})
    monkeypatch.setattr(control.os, 'environ', {})
    monkeypatch.setattr(control.os, 'initgroups', Mock())
    monkeypatch.setattr(control.os, 'setgid', Mock())
    monkeypatch.setattr(control.os, 'setuid', lambda uid: identity.__setitem__(0, uid))
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        {'7': props()}, {'7': props()}, {'8' if source_changed else '7': props()}]))
    def prepare():
        assert identity[0] == 1000
        assert control.os.environ == {'fixture': 'parent'}
        return 300
    operation = Mock(side_effect=prepare)
    monkeypatch.setattr(control, 'prepare_continuous_activity', operation)
    if source_changed:
        with pytest.raises(control.SessionError, match='source-changed'):
            control.execute('parent-continuous-activity')
    else:
        assert control.execute('parent-continuous-activity') == {
            'operation': 'parent-continuous-activity', 'outcome': 'passed',
            'interface': 'system session', 'idle_delay_seconds': 0,
            'previous_idle_delay_seconds': 300}
    operation.assert_called_once_with()


@pytest.mark.parametrize('fault', [None, 'enabled', 'boolean', 'missing', 'out-of-range'])
def test_continuous_activity_controller_requires_exact_readback(monkeypatch, fault):
    result = {'operation': 'parent-continuous-activity', 'outcome': 'passed',
              'interface': 'system session', 'idle_delay_seconds': 0,
              'previous_idle_delay_seconds': 300}
    if fault == 'enabled': result['idle_delay_seconds'] = 300
    if fault == 'boolean': result['idle_delay_seconds'] = False
    if fault == 'missing': del result['previous_idle_delay_seconds']
    if fault == 'out-of-range': result['previous_idle_delay_seconds'] = 4294967296
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    if fault:
        with pytest.raises(control.SessionError, match='response'):
            control.observe(transport, 'parent-continuous-activity')
    else:
        assert control.observe(transport, 'parent-continuous-activity') == result
    transport.call.assert_called_once()
    assert transport.call.call_args.args[0] == [
        '/usr/bin/python3', '-I', '-', 'parent-continuous-activity']


@pytest.mark.parametrize('operation', ['session-menu-toggle', 'session-menu-power',
                                       'session-menu', 'switch-user', 'logout', 'logout-confirm'])
def test_removed_shell_gui_operations_cannot_execute(operation):
    assert operation not in OPERATIONS
    ui = ui_for(Node())
    with pytest.raises(UiError, match='operation'):
        ui.run(operation, '')


@pytest.mark.parametrize('binding', ['parent-logout', 'standard-switch-user',
                                    'parent-return-greeter', 'standard-return-greeter',
                                    'child-switch-user'])
def test_controller_requires_command_result_over_guarded_transport(binding):
    role, action = control.BINDINGS[binding]
    expected = {'operation': binding, 'outcome': 'passed', 'interface': 'system session',
                'source_retained': action != 'logout', 'destination': 'greeter'}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(expected).encode()))
    assert control.observe(transport, binding) == expected
    assert transport.call.call_args.args[0] == ['/usr/bin/python3', '-I', '-', binding]
    assert transport.call.call_args.kwargs['input'] == __import__('pathlib').Path(control.__file__).read_bytes()
    transport.call.return_value = b'{}'
    with pytest.raises(control.SessionError, match='response'):
        control.observe(transport, binding)


LEAF = r'''
use strict;
use warnings;
use JSON::PP;
our ($block, $fault) = @ARGV;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
package main;
require onpc_desktop_session;
my $journey = onpc_journey->new(prefix => 'unit', review => 0, exchange => sub {
    push @events, ['seen', $_[0]];
    return {};
});
my $desktop = $journey->seen('desktop');
$desktop = {} if $fault eq 'stale';
@events = ();
my $ok = eval {
    if ($block eq 'switch_user') {
        onpc_desktop_session::switch_user($journey, $desktop);
        onpc_desktop_session::switch_user($journey, $desktop) if $fault eq 'replay';
    } else {
        onpc_desktop_session::log_out($journey, $desktop);
        onpc_desktop_session::log_out($journey, $desktop) if $fault eq 'replay';
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('block', ['switch_user', 'log_out'])
@pytest.mark.parametrize('fault', ['', 'stale', 'replay'])
def test_session_workers_consume_fresh_desktop_proofs_once(block, fault):
    result = json.loads(run_perl(LEAF, block, fault).stdout)
    assert result['ok'] == (not fault)
    expected = ([['seen', 'switch-user'], ['seen', 'gdm-switched']] if block == 'switch_user'
                else [['seen', 'logout'], ['seen', 'gdm-logged-out']])
    assert result['events'] == ([] if fault == 'stale' else expected)


@pytest.mark.parametrize('fault', ['', 'stale', 'replay'])
@pytest.mark.parametrize('stage', ['repeat-desktop', 'repeat-parent-desktop'])
def test_switch_after_parent_work_consumes_the_new_desktop_proof(fault, stage):
    program = LEAF.replace("seen('desktop')", f"seen('{stage}')").replace(
        'switch_user($journey, $desktop)', f"switch_user($journey, $desktop, '{stage}')")
    result = json.loads(run_perl(program, 'switch_user', fault).stdout)
    assert result['ok'] == (not fault)
    assert result['events'] == ([] if fault == 'stale' else
        [['seen', 'switch-user'], ['seen', 'gdm-switched']])


@pytest.mark.parametrize('action', ['logout', 'switch-user', 'lock'])
def test_complete_worker_matches_the_selected_plan_and_powers_off(action):
    from desktop_session import LOGOUT_PLAN, SWITCH_PLAN
    result = json.loads(run_perl(RUN_PROBE, action).stdout)
    if action == 'lock':
        assert not result['ok']
        assert not result['events']
        return
    assert result['ok']
    plan = LOGOUT_PLAN if action == 'logout' else SWITCH_PLAN
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == list(plan.screen_tags)
    assert result['events'].count(['secret']) == 1
    assert result['events'][-1] == ['power', 'off']


def test_plans_declare_every_stage_and_keep_prefixes_distinct():
    from desktop_session import LOGOUT_PLAN, SWITCH_PLAN
    for plan in (LOGOUT_PLAN, SWITCH_PLAN):
        assert set(plan.phases) == set(plan.stages)
        assert set(plan.advance_after) <= set(plan.screen_tags)
        assert plan.advance_after['desktop'] == 'step-2'
    assert LOGOUT_PLAN.prefix != SWITCH_PLAN.prefix
    assert LOGOUT_PLAN.worker_mode != SWITCH_PLAN.worker_mode


def test_session_qualification_uses_installed_snapshot_and_separate_attempts():
    import check_e2e_desktop_session as check
    from parent_setup_qualification import (DesktopLogoutQualification,
                                            DesktopSwitchQualification, KioskEntryQualification)

    # Installed qualification follows the checkout release, not a fixed old snapshot.
    version = json.loads((ROOT / 'data/app.json').read_bytes())['version']
    for qualification, mode in ((DesktopLogoutQualification, 'desktop_session_logout'),
                                (DesktopSwitchQualification, 'desktop_session_switch')):
        assert issubclass(qualification, KioskEntryQualification)
        context = SimpleNamespace()
        journey = qualification.journey(context, Mock())
        assert context.installed_snapshot == 'onpc-v' + version
        assert journey.plan.worker_mode == mode

    calls = []
    original = check.smoke
    try:
        check.smoke = lambda **kwargs: calls.append(kwargs) or 0
        assert check.main() == 0
    finally:
        check.smoke = original
    assert calls == [
        {'assets': check.ASSETS, 'provision_credentials': True,
         'desktop_session_logout': True},
        {'assets': check.ASSETS, 'provision_credentials': True,
         'desktop_session_switch': True},
    ]

    calls.clear()
    check.smoke = lambda **kwargs: calls.append(kwargs) or 1
    try:
        assert check.main() == 1
    finally:
        check.smoke = original
    assert calls == [{'assets': check.ASSETS, 'provision_credentials': True,
                      'desktop_session_logout': True}]


def lock_tree(monkeypatch, entry='curtain'):
    import accessible_ui as a
    window = Node(role='window', states=('showing', 'visible', 'sensitive', 'focused'))
    hint = Node('Click or press a key to unlock', 'label')
    recipient = Node(a.PARENT, 'label')
    field = Node('Password:', 'password text', states=(
        'showing', 'visible', 'sensitive', 'focused', 'editable'))
    field.get_child_count = Mock(side_effect=AssertionError('protected traversal'))
    field.getText = Mock(side_effect=AssertionError('protected text'))
    window.children = [hint] if entry == 'curtain' else [recipient, field]
    if entry == 'challenge': window.states.discard('focused')
    for child in window.children: child.parent = window
    shell = Node('gnome-shell', 'application', children=[window])
    root = Node(role='desktop frame', children=[shell])
    monkeypatch.setattr(a.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000))
    monkeypatch.setattr(a, 'Path', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=1000)))
    monkeypatch.setattr(control, 'sessions', lambda: {'7': props(locked='yes')})
    ui = ui_for(root)
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    ui._shell_provider_metadata = Mock(return_value={
        'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]})
    return ui, root, shell, window, recipient, field


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
def test_lock_surface_reads_public_identity_without_secret_input(monkeypatch, entry):
    ui, _, _, _, _, field = lock_tree(monkeypatch, entry)
    result = ui.run('parent-lock-' + entry, '')['lock']
    assert result == {'entry': entry, 'owner': 'fixture-parent', 'locked': True,
        'desktop_input_available': False, 'recipient': 'fixture-parent' if entry == 'challenge' else None,
        'surface_id': 'a' * 64, 'provider': ui._shell_provider_metadata.return_value}
    field.get_child_count.assert_not_called()
    field.getText.assert_not_called()
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['unlocked', 'wrong-session', 'wrong-seat', 'multiple-sessions',
    'multiple-windows', 'wrong-owner', 'foreign-password', 'foreign-focus', 'foreign-dialog',
    'duplicate-field', 'wrong-recipient', 'disabled-field', 'unfocused-field', 'defunct', 'incomplete'])
def test_lock_challenge_refuses_unsafe_surfaces_without_input(monkeypatch, fault):
    import accessible_ui as a
    ui, root, shell, window, recipient, field = lock_tree(monkeypatch, 'challenge')
    current = {'7': props(locked='yes')}
    if fault == 'unlocked': current['7']['LockedHint'] = 'no'
    elif fault == 'wrong-session': current['7']['User'] = '1001'
    elif fault == 'wrong-seat': current['7']['Seat'] = 'seat1'
    elif fault == 'multiple-sessions': current['8'] = props('1001', locked='yes')
    elif fault == 'multiple-windows': shell.children.append(Node(role='window'))
    elif fault == 'wrong-owner': shell.get_process_id = lambda: 200
    elif fault.startswith('foreign-'):
        node = Node(role={'foreign-password': 'password text', 'foreign-focus': 'text',
                          'foreign-dialog': 'dialog'}[fault])
        if fault == 'foreign-focus': node.states.add('focused')
        root.children.append(Node('other', 'application', children=[node]))
    elif fault == 'duplicate-field': window.children.append(Node(role='password text'))
    elif fault == 'wrong-recipient': recipient.name = a.OTHER_PARENT
    elif fault == 'disabled-field': field.states.discard('sensitive')
    elif fault == 'unfocused-field': field.states.discard('focused')
    elif fault == 'defunct': field.states.add('defunct')
    elif fault == 'incomplete': window.children.append(None)
    monkeypatch.setattr(control, 'sessions', lambda: current)
    with pytest.raises(a.UiError): ui.run('parent-lock-challenge', '')
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()
    ui.mate_challenge_identity.assert_not_called()


def test_curtain_proof_cannot_authorize_input_to_an_open_challenge(monkeypatch):
    import accessible_ui as a
    ui, _, _, _, _, _ = lock_tree(monkeypatch, 'challenge')
    with pytest.raises(a.UiError, match='lock-not-curtain'):
        ui.run('parent-lock-reveal-ready', '')


def test_other_lock_surface_diagnostic_preserves_refusal_without_private_text(monkeypatch, capsys):
    import accessible_ui as a
    ui, root, _, _, _, field = lock_tree(monkeypatch, 'challenge')
    foreign = Node('PRIVATE-CANARY', 'text', states=('showing', 'visible', 'focused'))
    root.children.append(Node('PRIVATE-APP-CANARY', 'application', children=[foreign]))
    with pytest.raises(a.UiError, match='ui:lock-other-surface'):
        ui.run('parent-lock-challenge', '')
    diagnostic = json.loads(capsys.readouterr().err)
    assert diagnostic == {'event': 'ui-lock-other-surface', 'count': 1, 'nodes': [
        {'role': 'text', 'focused': True, 'modal': False, 'same_shell_process': True}]}
    assert 'PRIVATE' not in json.dumps(diagnostic)
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()


def test_live_tree_refusal_projections_use_the_same_read_only_adapter(monkeypatch):
    ui, _, _, _, _, field = lock_tree(monkeypatch, 'challenge')
    assert ui.run('parent-lock-refusals', '')['lock'] == {
        'refused': ['session', 'surface-ambiguous', 'field-ambiguous', 'recipient']}
    field.action.do_action.assert_not_called()
    field.getText.assert_not_called()


@pytest.mark.parametrize('operation', ['parent-lock-refusals', 'parent-lock-recipient-refusals'])
@pytest.mark.parametrize('outcome', ['recovered', 'persistent', 'wrong-recipient'])
def test_lock_refusal_late_query_failure_restarts_complete_read(monkeypatch, operation, outcome):
    import accessible_ui as a
    ui, _, _, _, recipient, field = lock_tree(monkeypatch, 'challenge')
    field.get_text_iface = Mock(return_value=SimpleNamespace())
    ui.api.Text = SimpleNamespace(get_character_count=Mock(return_value=0))
    ui.query_errors = (LookupError,)
    ui.timeout = 2
    ticks = iter(range(1000))
    monkeypatch.setattr(a.time, 'monotonic', lambda: next(ticks) / 10)
    monkeypatch.setattr(a.time, 'sleep', lambda _: None)
    original = ui.shell_lock_snapshot
    reads = []

    def observe(uid, entry, **kwargs):
        reads.append(bool(kwargs))
        # A node disappears only after the first live tree and wrong-session
        # projection succeeded. Retrying only initial discovery cannot fix it.
        if kwargs and uid == 1000 and (outcome == 'persistent' or reads.count(True) == 2):
            if outcome == 'wrong-recipient':
                recipient.name = a.OTHER_PARENT
            raise LookupError('retired accessibility object')
        return original(uid, entry, **kwargs)

    ui.shell_lock_snapshot = observe
    if outcome == 'recovered':
        assert ui.run(operation, '')['lock']['refused']
        assert reads.count(False) >= 3  # initial, reacquired, independent final
    else:
        with pytest.raises(UiError, match='timeout|lock-recipient'):
            ui.run(operation, '')
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()
    field.getText.assert_not_called()


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
def test_lock_surface_binds_semantic_window_beneath_empty_shell_wrapper(monkeypatch, entry):
    ui, _, shell, window, _, field = lock_tree(monkeypatch, entry)
    wrapper = Node(role='window', children=[window])
    shell.children = [wrapper]
    wrapper.parent = shell
    result = ui.run('parent-lock-' + entry, '')['lock']
    assert result['entry'] == entry
    ui.mate_challenge_identity.assert_called_once_with(shell.get_process_id(), (shell, window))
    field.get_child_count.assert_not_called()
    field.getText.assert_not_called()


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
@pytest.mark.parametrize('fault', ['hint', 'recipient', 'password', 'focus', 'modal', 'dialog',
    'descendant-window', 'sibling-window', 'shared-window', 'shared-control', 'cycle',
    'owner-cycle', 'foreign-wrapper', 'duplicate-edge'])
def test_lock_wrapper_never_hides_competing_or_ambiguous_ownership(monkeypatch, entry, fault):
    import accessible_ui as a
    ui, _, shell, window, _, field = lock_tree(monkeypatch, entry)
    wrapper = Node(role='window', children=[window])
    shell.children = [wrapper]
    wrapper.parent = shell
    if fault in ('hint', 'recipient', 'password', 'focus', 'modal', 'dialog'):
        extra = Node(role='label')
        if fault == 'hint': extra.name = 'Click or press a key to unlock'
        elif fault == 'recipient': extra.name = a.OTHER_PARENT
        elif fault == 'password': extra.role = 'password text'
        elif fault == 'focus': extra.states.add('focused')
        elif fault == 'modal': extra.states.add('modal')
        elif fault == 'dialog': extra.role = 'dialog'
        wrapper.children.append(extra)
    elif fault == 'descendant-window': window.children.append(Node(role='window'))
    elif fault == 'sibling-window': wrapper.children.append(Node(role='window'))
    elif fault == 'shared-window': shell.children.append(window)
    elif fault == 'shared-control': wrapper.children.append(window.children[0])
    elif fault == 'cycle': window.children.append(wrapper)
    elif fault == 'owner-cycle': wrapper.children.append(shell)
    elif fault == 'foreign-wrapper': wrapper.get_process_id = lambda: 200
    elif fault == 'duplicate-edge': wrapper.children.append(window)
    with pytest.raises(UiError): ui.run('parent-lock-' + entry, '')
    ui.mate_challenge_identity.assert_not_called()
    field.getText.assert_not_called()
    field.action.do_action.assert_not_called()
    window.component.grab_focus.assert_not_called()


def test_lock_replacement_under_unchanged_wrapper_cannot_release_reveal(monkeypatch):
    from ui_observations import UiObservations
    from private_artifacts import EvidenceError
    ui, _, shell, window, _, _ = lock_tree(monkeypatch)
    wrapper = Node(role='window', children=[window])
    shell.children = [wrapper]
    wrapper.parent = shell
    ui.mate_challenge_identity = lambda pid, targets: ('a' if targets[1] is window else 'b') * 64
    reader = UiObservations(SimpleNamespace())
    reader.call = lambda argv, *args, **kwargs: (json.dumps(ui.run(argv[3], '')).encode(), [])
    assert reader.observe('parent-lock-curtain')['lock']['surface_id'] == 'a' * 64
    replacement = Node(role='window', children=[Node('Click or press a key to unlock', 'label')],
                       states=('showing', 'visible', 'sensitive', 'focused'))
    wrapper.children = [replacement]
    replacement.parent = wrapper
    with pytest.raises(EvidenceError, match='lock-surface-changed'):
        reader.observe('parent-lock-reveal-ready')


@pytest.mark.parametrize('entry', ['curtain', 'challenge'])
@pytest.mark.parametrize('topology', ['ancestor', 'sibling', 'cycle', 'shared'])
def test_lock_ambiguity_diagnostic_preserves_refusal_and_private_text(
        monkeypatch, capsys, entry, topology):
    ui, _, shell, window, _, field = lock_tree(monkeypatch, entry)
    extra = Node('private-window-canary', 'window', children=[
        Node('private-label-canary', 'label')])
    if topology == 'ancestor':
        # An ancestor is ambiguous only when it has independent lock semantics.
        extra.children.append(Node('Click or press a key to unlock', 'label'))
    if topology in ('ancestor', 'cycle', 'shared'):
        extra.children.append(window)
        shell.children = [extra]
        window.parent = extra
        if topology == 'cycle': window.children.append(extra)
        if topology == 'shared': shell.children.append(window)
    else:
        shell.children.append(extra)
    extra.parent = shell
    ui.read_snapshot = Mock(wraps=ui.read_snapshot)
    with pytest.raises(UiError, match='lock-surface-ambiguous'):
        ui.run('parent-lock-' + entry, '')
    stderr = capsys.readouterr().err
    diagnostic = next(json.loads(line) for line in stderr.splitlines()
                      if line.startswith('{') and json.loads(line).get('event')
                      == 'ui-lock-window-ambiguity')
    assert diagnostic['window_count'] == 2 and not diagnostic['truncated']
    rows = diagnostic['windows']
    assert sorted(len(row['contains_windows']) for row in rows) == (
        [1, 1] if topology == 'cycle' else [0, 1] if topology != 'sibling' else [0, 0])
    if topology == 'shared': assert max(row['incoming_edges'] for row in rows) == 2
    if topology != 'cycle':
        assert sum(row['own_hints'] for row in rows) == int(entry == 'curtain') + int(topology == 'ancestor')
        assert sum(row['own_password_fields'] for row in rows) == int(entry == 'challenge')
        assert sum(row['own_parent_labels'] for row in rows) == int(entry == 'challenge')
    assert 'private-window-canary' not in stderr and 'private-label-canary' not in stderr
    ui.read_snapshot.assert_called_once_with(protect_text=True)
    ui.mate_challenge_identity.assert_not_called()
    field.getText.assert_not_called()
    field.get_child_count.assert_not_called()
    field.action.do_action.assert_not_called()
    window.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('unavailable', [False, True])
def test_lock_ambiguity_diagnostic_bounds_output_and_cannot_replace_failure(
        monkeypatch, capsys, unavailable):
    ui, _, shell, _, _, _ = lock_tree(monkeypatch)
    shell.children.extend(Node('private-canary', 'window') for _ in range(24))
    if unavailable:
        ui.lock_window_diagnostic = Mock(side_effect=RuntimeError('private-error-canary'))
    with pytest.raises(UiError, match='lock-surface-ambiguous'):
        ui.run('parent-lock-curtain', '')
    stderr = capsys.readouterr().err
    if unavailable:
        assert 'ui:lock-window-diagnostic-unavailable' in stderr
    else:
        diagnostic = next(json.loads(line) for line in stderr.splitlines()
                          if line.startswith('{') and json.loads(line).get('event')
                          == 'ui-lock-window-ambiguity')
        assert diagnostic['window_count'] == 25 and diagnostic['truncated']
        assert len(diagnostic['windows']) == 16 and len(stderr) < 8192
    assert 'private-canary' not in stderr and 'private-error-canary' not in stderr
    ui.mate_challenge_identity.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'entry', 'owner', 'locked', 'desktop', 'recipient',
                                  'identity', 'provider', 'extra', 'replacement'])
def test_lock_decoder_validates_public_result_and_pins_surface(monkeypatch, fault):
    from ui_observations import UiObservations
    from private_artifacts import EvidenceError
    ui, _, _, _, _, _ = lock_tree(monkeypatch, 'curtain')
    curtain = ui.run('parent-lock-curtain', '')
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(return_value=(json.dumps(curtain).encode(), []))
    assert reader.observe('parent-lock-curtain')['lock']['surface_id'] == 'a' * 64
    result = {**curtain, 'operation': 'parent-lock-challenge', 'lock': {
        **curtain['lock'], 'entry': 'challenge', 'recipient': 'fixture-parent'}}
    changes = {'entry': ('entry', 'curtain'), 'owner': ('owner', 'other'),
        'locked': ('locked', False), 'desktop': ('desktop_input_available', True),
        'recipient': ('recipient', 'other'), 'identity': ('surface_id', 'bad'),
        'provider': ('provider', {}), 'extra': ('private', 'canary'),
        'replacement': ('surface_id', 'b' * 64)}
    if fault:
        key, value = changes[fault]
        result['lock'][key] = value
    reader.call.return_value = (json.dumps(result).encode(), [])
    if fault:
        with pytest.raises((EvidenceError, UiError)): reader.observe('parent-lock-challenge')
    else:
        assert reader.observe('parent-lock-challenge')['lock']['recipient'] == 'fixture-parent'


@pytest.mark.parametrize('supplied', [False, True])
def test_lock_worker_complete_sequence_and_refusal_stops(supplied):
    from desktop_session import LOCK_PLAN, SUPPLIED_LOCK_PLAN
    plan = SUPPLIED_LOCK_PLAN if supplied else LOCK_PLAN
    program = RUN_PROBE.replace("onpc_desktop_session::run(sub {",
        "onpc_desktop_session::qualify_lock(sub {").replace('}, $action);', '}, $action);')
    result = json.loads(run_perl(program, '1' if supplied else '0').stdout)
    assert result['ok'], result
    events = result['events']
    assert [event[1] for event in events if event[0] == 'stage'] == list(plan.screen_tags)
    assert events.count(['secret']) == 1  # Fresh login only; lock input is never secret.
    assert events.count(['key', 'spc']) == 1
    assert events.count(['key', 'super-l']) == int(supplied)
    assert events[-1] == ['power', 'off']
    for stage in ('unlocked-refused', 'lock-ready', 'curtain', 'reveal-ready', 'challenge', 'lock-refusals'):
        failed = program.replace("push @events, ['stage', $_[0]];",
            "push @events, ['stage', $_[0]]; die 'guard' if $_[0] eq '" + stage + "';")
        result = json.loads(run_perl(failed, '1' if supplied else '0').stdout)
        assert not result['ok']
        expected = events[:events.index(['stage', stage]) + 1]
        assert result['events'] == expected


def test_lock_qualification_separate_attempts_and_registered_transport(monkeypatch):
    import check_e2e_lock_surface as check
    import check_graphical_smoke as smoke
    from desktop_session import LOCK_PLAN, SUPPLIED_LOCK_PLAN
    from parent_setup_qualification import LockSurfaceQualification, SuppliedLockSurfaceQualification
    from tools import test_commands
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert [value['lock_surface'] for value in calls] == ['command', 'supplied']
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 1)
    calls.clear()
    assert check.main() == 1 and len(calls) == 1
    for cls, plan in ((LockSurfaceQualification, LOCK_PLAN),
                      (SuppliedLockSurfaceQualification, SUPPLIED_LOCK_PLAN)):
        context = SimpleNamespace()
        journey = cls.journey(context, Mock())
        assert journey.plan is plan
        assert context.installed_snapshot.startswith('onpc-v')
        assert set(plan.phases) == set(plan.stages)
        assert all(tag[7:] in control.BINDINGS for tag in plan.screen_tags.values()
                   if tag.startswith('system:'))
        assert all(tag[3:] in OPERATIONS for tag in plan.screen_tags.values() if tag.startswith('ui:'))
    # Invalid mixed modes fail before credentials, storage, VM or other preparation.
    with pytest.raises(RuntimeError, match='lock-surface-prerequisites'):
        smoke.main(assets=check.ASSETS, provision_credentials=True,
                   lock_surface='command', desktop_session_switch=True)
    prepare = Mock(return_value='prepared')
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', prepare)
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    assert test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_lock_surface'])
    prepare.assert_called_once()


def test_lock_read_reacquires_delayed_and_incomplete_transitions(monkeypatch):
    import accessible_ui as a
    ui, _, _, window, _, field = lock_tree(monkeypatch, 'challenge')
    original = ui.shell_lock_snapshot
    reads = []

    def observe(*args, **kwargs):
        reads.append(1)
        if len(reads) == 1: return None
        if len(reads) == 2: raise a.UiError('ui:incomplete-tree')
        return original(*args, **kwargs)

    ui.shell_lock_snapshot = observe
    ui.timeout = 2
    assert ui.run('parent-lock-challenge', '')['lock']['entry'] == 'challenge'
    assert len(reads) == 3
    field.action.do_action.assert_not_called()
    window.component.grab_focus.assert_not_called()


def test_already_open_lock_observation_has_no_reveal_input(monkeypatch):
    from journey_blocks import lock_challenge
    from ui_observations import UiObservations
    ui, _, _, _, _, _ = lock_tree(monkeypatch, 'challenge')
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(return_value=(json.dumps(ui.run('parent-lock-challenge', '')).encode(), []))
    assert reader.observe('parent-lock-challenge')['lock']['entry'] == 'challenge'
    assert lock_challenge('again-', entry='challenge') == {'again-challenge': 'ui:parent-lock-challenge'}
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $journey = onpc_journey->new(exchange => sub { push @events, ['stage', $_[0]]; return {}; },
    prefix => 'independent', review => 0);
onpc_desktop_session::observe_lock($journey, 'challenge');
print encode_json({events => \@events});
'''
    assert json.loads(run_perl(program, '0').stdout)['events'] == [['stage', 'challenge']]


@pytest.mark.parametrize('fault', ['', 'nonempty', 'missing-text', 'unfocused', 'wrong-user', 'stale'])
def test_lock_recipient_reads_only_empty_count_after_identity_guards(monkeypatch, fault):
    import accessible_ui as a
    ui, _, _, _, recipient, field = lock_tree(monkeypatch, 'challenge')
    interface = SimpleNamespace()
    field.get_text_iface = Mock(return_value=None if fault == 'missing-text' else interface)
    ui.api.Text = SimpleNamespace(get_character_count=Mock(return_value=1 if fault == 'nonempty' else 0))
    if fault == 'unfocused': field.states.discard('focused')
    elif fault == 'wrong-user': recipient.name = a.OTHER_PARENT
    elif fault == 'stale': field.states.add('defunct')
    if fault:
        with pytest.raises(UiError): ui.run('parent-lock-recipient-qualified', '')
    else:
        result = ui.run('parent-lock-recipient-qualified', '')['lock']
        assert result['empty'] is result['masked'] is result['focused'] is True
        assert result['challenge_id'] == 'a' * 64
        ui.api.Text.get_character_count.assert_called_once_with(interface)
    if fault in ('unfocused', 'wrong-user', 'stale'):
        field.get_text_iface.assert_not_called()
    field.getText.assert_not_called()
    field.get_child_count.assert_not_called()
    field.action.do_action.assert_not_called()
    field.component.grab_focus.assert_not_called()


def recipient_reader(monkeypatch):
    from ui_observations import UiObservations
    ui, _, _, _, _, field = lock_tree(monkeypatch, 'challenge')
    field.get_text_iface = Mock(return_value=SimpleNamespace())
    ui.api.Text = SimpleNamespace(get_character_count=Mock(return_value=0))
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(side_effect=lambda argv, *args, **kwargs:
        (json.dumps(ui.run(argv[3], '')).encode(), []))
    return ui, reader


@pytest.mark.parametrize('fault', ['', 'gdm', 'reordered', 'intervening', 'stale', 'slow',
                                  'replacement', 'replay', 'nonempty-response'])
def test_lock_recipient_decoder_orders_two_fresh_same_challenge_proofs(monkeypatch, fault):
    from private_artifacts import EvidenceError
    import ui_observations as observations
    ui, reader = recipient_reader(monkeypatch)
    clock = [10.0]
    monkeypatch.setattr(observations.time, 'monotonic', lambda: clock[0])
    reader.observe('parent-lock-challenge')
    if fault in ('gdm', 'reordered'):
        reader.last_operation = 'gdm-parent-recipient' if fault == 'gdm' else None
        with pytest.raises(EvidenceError, match='lock-recipient-order'):
            reader.observe('parent-lock-recipient-qualified')
        assert reader.call.call_count == 1
        return
    first = reader.observe('parent-lock-recipient-qualified')
    assert first['lock']['empty'] is True
    if fault == 'intervening': reader.observe('parent-lock-challenge')
    elif fault == 'stale': clock[0] = 40.0
    elif fault == 'replacement':
        ui.mate_challenge_identity = lambda pid, nodes: ('b' if len(nodes) == 3 else 'a') * 64
    elif fault in ('slow', 'nonempty-response'):
        original = reader.call.side_effect
        def response(*args, **kwargs):
            raw, prompts = original(*args, **kwargs)
            if fault == 'slow': clock[0] += 30.0
            if fault == 'nonempty-response':
                result = json.loads(raw)
                result['lock']['empty'] = False
                raw = json.dumps(result).encode()
            return raw, prompts
        reader.call.side_effect = response
    if fault and fault != 'replay':
        with pytest.raises(EvidenceError): reader.observe('parent-lock-recipient-rechecked')
        calls = reader.call.call_count
        with pytest.raises(EvidenceError, match='previous-failure'):
            reader.observe('parent-lock-recipient-qualified')
        assert reader.call.call_count == calls
    else:
        assert reader.observe('parent-lock-recipient-rechecked')['lock']['challenge_id'] == 'a' * 64
        if fault == 'replay':
            with pytest.raises(EvidenceError, match='lock-recipient-order'):
                reader.observe('parent-lock-recipient-rechecked')


def test_live_lock_recipient_refusals_project_field_state_without_input(monkeypatch):
    import accessible_ui as a
    ui, reader = recipient_reader(monkeypatch)
    assert reader.observe('parent-lock-recipient-refusals')['lock'] == {
        'refused': list(a.LOCK_RECIPIENT_REFUSALS)}


def test_lock_recipient_worker_sequence_refusals_and_registration(monkeypatch):
    from desktop_session import LOCK_RECIPIENT_PLAN as plan
    from parent_setup_qualification import LockRecipientQualification
    import check_e2e_lock_recipient as check
    from tools import test_commands
    program = RUN_PROBE.replace('onpc_desktop_session::run(sub {',
        'onpc_desktop_session::qualify_lock_recipient(sub {').replace('}, $action);', '});')
    program = program.replace("return {observed => $_[0]} if $_[0] =~ /recipient-", """
        return {observed => $_[0], lock_recipient => {surface => 'lock', role => 'parent',
            challenge_id => 'a' x 64}} if $_[0] =~ /\\Alock-recipient-/;
        return {observed => $_[0]} if $_[0] =~ /recipient-""")
    result = json.loads(run_perl(program, '').stdout)
    assert result['ok'], result
    events = result['events']
    assert [row[1] for row in events if row[0] == 'stage'] == list(plan.screen_tags)
    assert events.count(['secret']) == 1 and events.count(['key', 'spc']) == 1
    assert events[-1] == ['power', 'off']
    for stage in plan.screen_tags:
        failed = program.replace("push @events, ['stage', $_[0]];",
            "push @events, ['stage', $_[0]]; die 'guard' if $_[0] eq '" + stage + "';")
        result = json.loads(run_perl(failed, '').stdout)
        assert not result['ok']
        assert result['events'] == events[:events.index(['stage', stage]) + 1]
    context = SimpleNamespace()
    assert LockRecipientQualification.journey(context, Mock()).plan is plan
    assert context.installed_snapshot.startswith('onpc-v')
    assert set(plan.phases) == set(plan.stages)
    assert all(tag[3:] in OPERATIONS for tag in plan.screen_tags.values() if tag.startswith('ui:'))
    smoke = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 0
    smoke.assert_called_once_with(assets=check.ASSETS, provision_credentials=True, lock_surface='recipient')
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', Mock(return_value='prepared'))
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    assert test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_lock_recipient'])


@pytest.mark.parametrize('fault', ['gdm', 'replacement', 'review'])
def test_lock_worker_refuses_gdm_replaced_and_review_proofs(fault):
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $journey = onpc_journey->new(prefix => 'unit', review => $action eq 'review' ? 1 : 0,
    exchange => sub {
        push @events, ['stage', $_[0]];
        return {observed => $_[0]} if $action eq 'gdm';
        return {observed => $_[0], lock_recipient => {surface => 'lock', role => 'parent',
            challenge_id => scalar(($_[0] =~ /rechecked/ ? 'b' : 'a') x 64)}};
    });
my $ok = eval { onpc_desktop_session::lock_recipient($journey); 1; };
my $count = scalar @events;
my $retry = eval { onpc_desktop_session::lock_recipient($journey); 1; };
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0,
    count => $count, final_count => scalar @events});
'''
    result = json.loads(run_perl(program, fault).stdout)
    assert not result['ok'] and not result['retry']
    assert result['count'] == result['final_count']


def test_lock_recipient_shared_fragment_supports_independent_named_callers():
    from journey_blocks import lock_recipient
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $journey = onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {
    push @events, ['stage', $_[0]];
    return {observed => $_[0], lock_recipient => {surface => 'lock', role => 'parent',
        challenge_id => 'a' x 64}};
});
onpc_desktop_session::lock_recipient($journey, 'again-');
print encode_json({events => \@events});
'''
    events = json.loads(run_perl(program, '').stdout)['events']
    stages = lock_recipient('again-')
    assert events == [['stage', stage] for stage in stages]
    assert list(stages.values()) == ['ui:parent-lock-recipient-qualified', 'ui:parent-lock-recipient-rechecked']


@pytest.mark.parametrize('fault', ['', 'parent-label', 'parent-session', 'nonempty'])
def test_child_lock_identity_survives_every_adapter_layer(monkeypatch, fault):
    import accessible_ui as a
    from ui_observations import UiObservations
    ui, _, _, _, recipient, field = lock_tree(monkeypatch, 'challenge')
    recipient.name = a.PARENT if fault == 'parent-label' else a.CHILD
    monkeypatch.setattr(a.os, 'getuid', lambda: 1002)
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=1002 if name == control.ACCOUNTS['child'] else 1000))
    monkeypatch.setattr(a, 'Path', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=1002)))
    monkeypatch.setattr(control, 'sessions', lambda: {'7': props(
        '1000' if fault == 'parent-session' else '1002', locked='yes')})
    field.get_text_iface = Mock(return_value=SimpleNamespace())
    ui.api.Text = SimpleNamespace(get_character_count=Mock(return_value=1 if fault == 'nonempty' else 0))
    reader = UiObservations(SimpleNamespace())
    reader.call = Mock(side_effect=lambda argv, *args, **kwargs:
        (json.dumps(ui.run(argv[3], '')).encode(), []))
    if fault:
        with pytest.raises(UiError): reader.observe('child-lock-challenge' if fault != 'nonempty'
                                                 else 'child-lock-recipient-refusals')
    else:
        assert reader.observe('child-lock-challenge')['lock']['recipient'] == 'fixture-child'
        for check in ('qualified', 'rechecked'):
            result = reader.observe('child-lock-recipient-' + check)['lock']
            assert result['owner'] == result['recipient'] == 'fixture-child'
            assert result['empty'] is result['masked'] is result['focused'] is True
        assert set(a.CHILD_LOCK_OPERATIONS) <= a.CHILD_DESKTOP_OPERATIONS
    field.getText.assert_not_called()
    field.action.do_action.assert_not_called()


def unlock_probe(plan, *, denied=False):
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $plan = decode_json($ARGV[1]);
my $ok = eval {
    onpc_desktop_session::qualify_retained_unlock(sub {
        my ($stage) = @_;
        push @events, ['stage', $stage];
        die 'guard' if $stage eq $action;
        for my $id (keys %{$plan->{challenges}}) {
            my ($role, $first, $second) = @{$plan->{challenges}{$id}};
            if ($stage eq $first || $stage eq $second) {
                return {observed => $stage, challenge => {id => $id, role => $role,
                    surface => 'gdm', check => $stage eq $first ? 'qualified' : 'rechecked'}};
            }
        }
        return {observed => $stage, lock_recipient => {surface => 'lock', role => 'child',
            challenge_id => 'a' x 64}} if $stage =~ /\Alock-recipient-(?:qualified|rechecked)\z/;
        return {observed => $stage, ui_focused => 1} if $stage =~ /(?:greeter|list)$/;
        return {observed => $stage};
    }, $plan->{retained}, $plan->{invocations}, $plan->{challenges});
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    if denied:
        program = program.replace('qualify_retained_unlock', 'qualify_retained_denial')
        program = program.replace('return {observed => $stage};',
            "return {observed => $stage, gdm_return_state => 'account-list'} if $stage eq 'denied-return-state'; return {observed => $stage};")
    return program, json.dumps({'retained': int(plan.worker_mode in ('retained_unlock_success', 'retained_unlock_denied')),
                               'invocations': plan.invocations, 'challenges': plan.challenges})


@pytest.mark.parametrize('retained', [False, True])
def test_unlock_actual_worker_order_and_every_refusal_stop(retained):
    from desktop_session import CHILD_UNLOCK_PLAN, RETAINED_UNLOCK_PLAN
    plan = RETAINED_UNLOCK_PLAN if retained else CHILD_UNLOCK_PLAN
    if retained:
        # GDM reauthenticates the retained session on its own surface. Selecting
        # the account does not activate the child's private lock-screen bus.
        assert plan.screen_tags['retained-recipient-qualified'] == 'ui:gdm-child-recipient'
        assert plan.challenge_at('retained-recipient-rechecked') == {
            'id': 'retained-login', 'role': 'child', 'surface': 'gdm', 'check': 'rechecked'}
        stages = list(plan.screen_tags)
        after_selection = stages[stages.index('retained-focused') + 1:]
        assert not any(plan.screen_tags[stage].startswith('ui:child-lock-')
                       for stage in after_selection)
    else:
        assert plan.screen_tags['lock-recipient-qualified'] == 'ui:child-lock-recipient-qualified'
    program, binding = unlock_probe(plan)
    result = json.loads(run_perl(program, '', binding).stdout)
    assert result['ok'], result
    events = result['events']
    assert [row[1] for row in events if row[0] == 'stage'] == list(plan.screen_tags)
    assert events.count(['secret']) == 3
    assert events.count(['key', 'spc']) == 1
    assert events[-1] == ['power', 'off']
    for stage in plan.screen_tags:
        failure = json.loads(run_perl(program, stage, binding).stdout)
        assert not failure['ok']
        assert failure['events'] == events[:events.index(['stage', stage]) + 1]
    assert all(tag[3:] in OPERATIONS if tag.startswith('ui:') else tag[7:] in control.BINDINGS
               for tag in plan.screen_tags.values())


@pytest.mark.parametrize('retained', [False, True])
@pytest.mark.parametrize('denied', [False, True])
def test_unlock_recorder_constructor_and_worker_titles(tmp_path, monkeypatch, retained, denied):
    from unittest.mock import MagicMock
    from installed_journey import record_installed_journey, matched_screens
    from private_artifacts import EvidenceError
    from desktop_session import (RetainedUnlockJourney, CHILD_UNLOCK_PLAN, RETAINED_UNLOCK_PLAN,
                                 RetainedDenialJourney, CHILD_DENIAL_PLAN, RETAINED_DENIAL_PLAN)
    plan = (RETAINED_DENIAL_PLAN if retained else CHILD_DENIAL_PLAN) if denied else (
        RETAINED_UNLOCK_PLAN if retained else CHILD_UNLOCK_PLAN)
    journey_type = RetainedDenialJourney if denied else RetainedUnlockJourney
    program, binding = unlock_probe(plan, denied=denied)
    program = program.replace('sub record_info { }',
                              "sub record_info { push @main::events, ['title', $_[0]]; }")
    events = json.loads(run_perl(program, '', binding).stdout)['events']
    titles = [{'title': row[1], 'result': 'ok'} for row in events if row[0] == 'title']
    observations = []
    for stage, tag in plan.screen_tags.items():
        item = {'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
            'operation': tag.split(':', 1)[1], 'outcome': 'passed'}}
        if plan.challenge_at(stage): item['challenge'] = plan.challenge_at(stage)
        observations.append(item)
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': titles}))
    assert [item['stage'] for item in matched_screens(tmp_path, plan, observations)] == list(plan.screen_tags)
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    recorder = MagicMock(assertion=Mock())
    context.recorder = recorder
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is journey_type and journey.plan is plan
        assert options['validate'].__self__ is journey and options['authenticate'] is True
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(recorder, context, plan, journey_type=journey_type)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


@pytest.mark.parametrize('stage', ['returned-activity', 'usable-activity'])
@pytest.mark.parametrize('fault', ['', 'replacement', 'changed', 'missing'])
def test_unlock_real_step_preserves_activity_before_reply(tmp_path, stage, fault):
    from desktop_session import RetainedUnlockJourney, RETAINED_UNLOCK_PLAN as plan
    from private_artifacts import EvidenceError
    value = {'binding': 'native-primary', 'pid': 123, 'endpoint': [':1.50', '/activity'],
        'state': {'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft',
                  'score': 'Moves: 0; token: 0'}}
    journey = RetainedUnlockJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    if fault != 'missing': journey.check_activity('activity-capture', {'ui': {'activity': value}})
    current = json.loads(json.dumps(value))
    value['state'].clear()  # Captured values must not alias the decoder's mutable reply.
    if fault == 'replacement': current['endpoint'][1] = '/replacement'
    if fault == 'changed': current['state']['draft'] = 'lost work'
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'overlay-native-activity', 'activity': current}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert journey.failed and not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['comparison']['same_window'] is True


@pytest.mark.parametrize('fault', ['', 'gdm', 'wrong-role', 'replacement', 'ack', 'review', 'typing'])
def test_sealed_lock_input_refuses_foreign_proofs_and_never_replays(fault):
    program = RUN_PROBE[:RUN_PROBE.index('my $ok = eval')] + r'''
my $journey = onpc_journey->new(prefix => 'independent', review => $action eq 'review' ? 1 : 0,
    exchange => sub {
        my ($stage) = @_;
        push @events, ['stage', $stage];
        die 'ack-failed' if $action eq 'ack' && $stage =~ /rechecked/;
        return {observed => $stage, challenge => {surface => 'gdm'}} if $action eq 'gdm';
        return {observed => $stage, lock_recipient => {surface => 'lock',
            role => ($action eq 'wrong-role' ? 'parent' : 'child'),
            challenge_id => scalar(($action eq 'replacement' && $stage =~ /rechecked/ ? 'b' : 'a') x 64)}};
    });
my $ok = eval { onpc_password::enter_lock_password($journey, 'child'); 1; };
my $count = scalar @events;
my $retry = eval { onpc_password::enter_lock_password($journey, 'child'); 1; };
print encode_json({ok => $ok ? 1 : 0, retry => $retry ? 1 : 0,
    count => $count, events => \@events});
'''
    if fault == 'typing':
        program = program.replace("push @main::events, ['secret'];", "push @main::events, ['secret']; die 'uncertain';")
    result = json.loads(run_perl(program, fault).stdout)
    assert bool(result['ok']) == (not fault), result
    assert not result['retry'] and result['count'] == len(result['events'])
    assert result['events'].count(['secret']) == (1 if fault in ('', 'typing') else 0)
    assert not any(row[0] == 'key' for row in result['events'])


def test_unlock_registration_prepares_vm_bound_inputs_and_stops_second_attempt(monkeypatch):
    import check_e2e_retained_unlock_success as check
    from desktop_session import CHILD_UNLOCK_PLAN, RETAINED_UNLOCK_PLAN
    from parent_setup_qualification import ChildUnlockQualification, RetainedUnlockQualification
    from tools import test_commands
    for cls, plan in ((ChildUnlockQualification, CHILD_UNLOCK_PLAN),
                      (RetainedUnlockQualification, RETAINED_UNLOCK_PLAN)):
        context = SimpleNamespace()
        assert cls.journey(context, Mock()).plan is plan
        assert context.installed_snapshot.startswith('onpc-v')
        assert set(plan.phases) == set(plan.stages)
        assert plan.activity_checks == {'returned-activity': ('activity-capture', 'same'),
                                       'usable-activity': ('activity-capture', 'same')}
    smoke = Mock(side_effect=[0, 0])
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 0
    assert [call.kwargs['lock_surface'] for call in smoke.call_args_list] == ['child-success', 'retained-success']
    smoke = Mock(return_value=1)
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 1 and smoke.call_count == 1
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', Mock(return_value='prepared'))
    command = test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_retained_unlock_success'])
    assert any(value.endswith('/vm_artifacts.py') for value in command)


@pytest.mark.parametrize('retained', [False, True])
def test_retained_denial_actual_worker_order_and_every_refusal_stop(retained):
    from desktop_session import CHILD_DENIAL_PLAN, RETAINED_DENIAL_PLAN
    plan = RETAINED_DENIAL_PLAN if retained else CHILD_DENIAL_PLAN
    program, binding = unlock_probe(plan, denied=True)
    result = json.loads(run_perl(program, '', binding).stdout)
    assert result['ok'], result
    events = result['events']
    assert [row[1] for row in events if row[0] == 'stage'] == list(plan.screen_tags)
    assert events.count(['secret']) == (4 if retained else 3)
    assert events.count(['key', 'spc']) == int(not retained)
    assert events.count(['key', 'esc']) == int(retained)
    assert events[-1] == ['power', 'off']
    for stage in plan.screen_tags:
        failure = json.loads(run_perl(program, stage, binding).stdout)
        assert not failure['ok']
        assert failure['events'] == events[:events.index(['stage', stage]) + 1]
    assert all(tag[3:] in OPERATIONS if tag.startswith('ui:') else tag[7:] in control.BINDINGS
               for tag in plan.screen_tags.values())
    stages = list(plan.screen_tags)
    assert stages.index('logout') < stages.index('fresh-desktop') < stages.index('zero-configured')
    assert stages.index('time-denied') < stages.index('denied-returned') < stages.index('retained-after')


@pytest.mark.parametrize('fault', ['', 'not-greeter', 'unlocked', 'active', 'missing', 'duplicate',
                                  'changed', 'unlocked-result', 'lost-other', 'uncertain'])
def test_enter_locked_activates_only_the_preserved_locked_child_once(monkeypatch, fault):
    before = {'7': props('1002', active='no', locked='yes'),
              '8': props('120', kind='greeter'), '9': props('1000', active='no', locked='yes')}
    after = {**before, '7': props('1002', locked='yes'), '8': props('120', active='no', kind='greeter')}
    if fault == 'not-greeter': before['8'] = props('1000')
    if fault == 'unlocked': before['7']['LockedHint'] = 'no'
    if fault == 'active': before['7']['Active'] = 'yes'
    if fault == 'missing': del before['7']
    if fault == 'duplicate': before['10'] = props('1002', active='no', locked='yes')
    rechecked = {key: dict(value) for key, value in before.items()}
    if fault == 'changed': rechecked['7']['Type'] = 'x11'
    if fault == 'unlocked-result': after['7']['LockedHint'] = 'no'
    if fault == 'lost-other': del after['9']
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[before, rechecked, after]))
    command = Mock(side_effect=RuntimeError('uncertain') if fault == 'uncertain' else None)
    monkeypatch.setattr(control, 'call', command)
    if fault:
        with pytest.raises((control.SessionError, RuntimeError)):
            control.enter_locked(SimpleNamespace(pw_uid=1002))
    else:
        assert control.enter_locked(SimpleNamespace(pw_uid=1002)) == {
            'source_retained': True, 'destination': 'locked'}
    assert command.call_count == int(fault in ('', 'unlocked-result', 'lost-other', 'uncertain'))
    if command.called: command.assert_called_once_with(['/usr/bin/loginctl', 'activate', '7'])


@pytest.mark.parametrize('fault', ['', 'generic', 'missing', 'duplicate', 'wrong-recipient',
    'replacement', 'order', 'password', 'unlocked', 'wrong-session', 'wrong-owner',
    'incomplete', 'defunct', 'foreign-dialog', 'ambiguous', 'wrapper', 'unfocused',
    'missing-title', 'duplicate-title'])
def test_actual_lock_time_denial_requires_specific_message_and_same_surface(monkeypatch, fault):
    import accessible_ui as a
    from ui_observations import UiObservations
    from private_artifacts import EvidenceError
    ui, root, shell, window, recipient, field = lock_tree(monkeypatch, 'challenge')
    recipient.name = a.PARENT if fault == 'wrong-recipient' else a.CHILD
    monkeypatch.setattr(a.os, 'getuid', lambda: 1002)
    monkeypatch.setattr(a.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1002))
    monkeypatch.setattr(a, 'Path', lambda _: SimpleNamespace(stat=lambda: SimpleNamespace(st_uid=1002)))
    current = {'7': props('1002', locked='yes')}
    if fault == 'unlocked': current['7']['LockedHint'] = 'no'
    if fault == 'wrong-session': current['7']['User'] = '1001'
    monkeypatch.setattr(control, 'sessions', lambda: current)
    window.children = [recipient]
    message = ('Sorry, that didn’t work. Please try again.' if fault == 'generic' else
               'Daily limit for screen time on this device has been reached. Resume tomorrow.')
    if fault != 'unfocused': window.states.add('focused')
    if fault != 'missing-title': window.children.append(Node('Screen Time Limit Reached', 'label'))
    if fault == 'duplicate-title': window.children.append(Node('Screen Time Limit Reached', 'label'))
    if fault != 'missing':
        label = Node(message, 'label')
        label.parent = window
        window.children.append(label)
    for node in window.children: node.parent = window
    if fault == 'password':
        window.children.append(field)
    elif fault == 'wrong-owner': shell.get_process_id = lambda: 200
    elif fault == 'incomplete': window.children.append(None)
    elif fault == 'defunct': recipient.states.add('defunct')
    elif fault == 'foreign-dialog': root.children.append(Node('other', 'application', children=[Node(role='dialog')]))
    elif fault == 'ambiguous': shell.children.append(Node(role='window'))
    elif fault == 'wrapper':
        wrapper = Node(role='window', children=[window])
        wrapper.parent = shell
        shell.children = [wrapper]
    if fault == 'duplicate':
        label = Node(message, 'label')
        label.parent = window
        window.children.append(label)
    reader = UiObservations(SimpleNamespace())
    reader.lock_surface_id = ('b' if fault == 'replacement' else 'a') * 64
    reader.last_operation = 'child-lock-challenge' if fault == 'order' else 'child-lock-reveal-ready'
    reader.call = Mock(side_effect=lambda argv, *args, **kwargs:
        (json.dumps(ui.run(argv[3], '')).encode(), []))
    if fault not in ('', 'wrapper', 'unfocused'):
        with pytest.raises((UiError, RuntimeError, EvidenceError)): reader.observe('child-lock-time-denied')
    else:
        result = reader.observe('child-lock-time-denied')['lock']
        assert result['reason'] == 'time-limit' and result['desktop_input_available'] is False
        assert result['entry'] == 'restriction' and result['authentication_blocked'] is True
        assert result['recipient'] is None
    field.getText.assert_not_called()
    field.action.do_action.assert_not_called()
    for node in window.children:
        if node is not None: node.action.do_action.assert_not_called()


def test_denial_registration_prepares_vm_inputs_and_stops_after_failure(monkeypatch):
    import check_e2e_retained_unlock as check
    from desktop_session import CHILD_DENIAL_PLAN, RETAINED_DENIAL_PLAN
    from parent_setup_qualification import ChildDenialQualification, RetainedDenialQualification
    from tools import test_commands
    for cls, plan in ((ChildDenialQualification, CHILD_DENIAL_PLAN),
                      (RetainedDenialQualification, RETAINED_DENIAL_PLAN)):
        context = SimpleNamespace()
        assert cls.journey(context, Mock()).plan is plan
        assert context.installed_snapshot.startswith('onpc-v')
    smoke = Mock(side_effect=[0, 0])
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 0
    assert [call.kwargs['lock_surface'] for call in smoke.call_args_list] == ['retained-denied', 'child-denied']
    smoke = Mock(return_value=1)
    monkeypatch.setattr(check, 'smoke', smoke)
    assert check.main() == 1 and smoke.call_count == 1
    monkeypatch.setattr(test_commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(test_commands, 'allocate_artifact_output', Mock(return_value='prepared'))
    command = test_commands.qualification_artifact_command(ROOT, 'integration', ['check_e2e_retained_unlock'])
    assert any(value.endswith('/vm_artifacts.py') for value in command)


@pytest.mark.parametrize('fault', ['', 'wrong-owner', 'unlocked', 'not-greeter', 'extra', 'bad-hash'])
def test_retained_locked_read_and_controller_decoder_preserve_identity(monkeypatch, fault):
    current = {'7': props('1000' if fault == 'wrong-owner' else '1002', active='no',
                          locked='no' if fault == 'unlocked' else 'yes'),
               '8': props('120', kind='user' if fault == 'not-greeter' else 'greeter')}
    monkeypatch.setattr(control, 'sessions', lambda: current)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1002))
    submit = Mock()
    monkeypatch.setattr(control, 'call', submit)
    if fault in ('wrong-owner', 'unlocked', 'not-greeter'):
        with pytest.raises(control.SessionError): control.execute('child-retained-locked')
    else:
        result = control.execute('child-retained-locked')
        assert result['locked'] is True
        if fault == 'extra': result['private'] = 'canary'
        if fault == 'bad-hash': result['session_sha256'] = 'bad'
        transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
        if fault:
            with pytest.raises(control.SessionError): control.observe(transport, 'child-retained-locked')
        else:
            assert control.observe(transport, 'child-retained-locked') == result
            current['7']['Type'] = 'x11'
            assert control.execute('child-retained-locked')['session_sha256'] != result['session_sha256']
    submit.assert_not_called()
