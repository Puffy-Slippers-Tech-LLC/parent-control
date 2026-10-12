"""TIME01 public identity, complete absence, elapsed bounds and durable refusals.

Only synthetic trees, clocks, transport doubles and private pytest files.
No real desktop, account/session command, socket, VM or shared mutable state.
"""

from dataclasses import FrozenInstanceError, replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
import countdown as sampling
import check_e2e_countdown as check
from countdown import CountdownObservation, check_countdown_balance
from countdown_qualification import CountdownJourney, PLAN, OFF_PLAN
from parent_setup_qualification import CountdownQualification, CountdownOffQualification
from countdown_animation import CountdownAnimationJourney, PLAN as ANIMATION_PLAN
from parent_setup_qualification import CountdownAnimationQualification
import check_e2e_operate_the_countdown_context_menu as animation_check
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import UiObservations
from tests.support.perl import run_perl


def value(present=True, *, text='00:14', at=20_000_000_000):
    return {'child': 'fixture-child', 'surface': 'desktop', 'present': present,
            'text': text if present else None, 'observed_monotonic_ns': at,
            'stable_ms': 0 if present else 2000}


def tree(monkeypatch, *, present=True):
    label = Node('00:14', 'label', identity='child-remaining-time')
    button = Node('Request time, 00:14', 'push button', children=[label],
                  identity='child-request-button')
    indicator = Node('Screen Time Remaining', 'panel', children=[button],
                     identity='child-screen-time-indicator')
    panel = Node('Activities', 'toggle button')
    shell = Node(role='application', identity=accessible_ui.CHILD_PANEL_APPLICATION,
                 children=[panel, *([indicator] if present else [])])
    indicator.get_application = Mock(return_value=shell)
    root = Node(role='desktop frame', children=[shell])
    ui = ui_for(root)
    ui.timeout = 4
    now = [10.0]
    monkeypatch.setattr(accessible_ui, 'time', SimpleNamespace(
        monotonic=lambda: now[0], monotonic_ns=lambda: round(now[0] * 1_000_000_000),
        sleep=lambda delay: now.__setitem__(0, now[0] + delay)))
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1001))
    monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 1001)
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', Mock())
    return ui, root, shell, panel, indicator, label, now


@pytest.mark.parametrize('text,interval', [('00:14', (840, 899)), ('01:00', (3600, 3659)),
    ('00:01', (61, 119)), ('60', (60, 60)), ('0', (0, 0))])
def test_horizontal_countdown_public_format(text, interval):
    assert accessible_ui.countdown_seconds(text) == interval


@pytest.mark.parametrize('text', ['00:00', '24:00', '0:14', '00:60', '61', '-1',
                                 '14m', '00:14 fixture-private-canary', None])
def test_unknown_or_unbounded_countdown_text_refuses(text):
    with pytest.raises(accessible_ui.UiError, match='countdown-text'):
        accessible_ui.countdown_seconds(text)


def test_positive_id_scoped_read_and_complete_stable_absence(monkeypatch):
    ui, root, shell, panel, indicator, label, now = tree(monkeypatch)
    first = ui.child_countdown(True)
    assert first == value(at=10_000_000_000)
    ui.invalidate_observation()
    shell.children.remove(indicator)
    absence = ui.child_countdown(False)
    assert absence['text'] is None and absence['stable_ms'] >= 2000
    assert absence['observed_monotonic_ns'] >= 12_000_000_000
    for node in (root, shell, panel, indicator, label):
        node.action.do_action.assert_not_called()
        node.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('present,fault', [
    (present, fault) for present in (True, False) for fault in (
        'wrong-account', 'inactive', 'wrong-surface', 'duplicate', 'wrong-owner',
        'incomplete', 'defunct', 'prompt')
    if present or fault not in ('wrong-surface', 'duplicate', 'wrong-owner')])
def test_wrong_stale_or_incomplete_reads_never_establish_countdown(monkeypatch, present, fault):
    ui, root, shell, panel, indicator, label, _ = tree(monkeypatch, present=present)
    ui.timeout = 0
    if fault == 'wrong-account': monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 1002)
    if fault == 'inactive':
        accessible_ui.require_active_launch_session.side_effect = accessible_ui.UiError('ui:launch-session')
    if fault == 'wrong-surface': shell.identity = 'foreign-application'
    if fault == 'duplicate':
        for _ in range(2):
            duplicate = Node('00:14', 'label', identity='child-remaining-time')
            duplicate.parent = shell
            shell.children.append(duplicate)
    if fault == 'wrong-owner': ui.owner_pids = lambda: {999}
    if fault == 'incomplete': shell.children.append(None)
    if fault == 'defunct': panel.states.add('defunct')
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='keyring')
    with pytest.raises(accessible_ui.UiError): ui.child_countdown(present)
    panel.action.do_action.assert_not_called()
    label.action.do_action.assert_not_called()


def test_absence_stability_restarts_after_incomplete_read(monkeypatch):
    ui, root, shell, _, _, _, now = tree(monkeypatch, present=False)
    calls = []
    def advance(delay):
        now[0] += delay
        calls.append(now[0])
        shell.children = [shell.children[0], None] if 10.8 <= now[0] < 11.2 else [shell.children[0]]
    monkeypatch.setattr(accessible_ui.time, 'sleep', advance)
    result = ui.child_countdown(False)
    assert result['stable_ms'] >= 2000 and now[0] >= 13.2
    assert ui.incomplete_observations


@pytest.mark.parametrize('operation', sorted(accessible_ui.COUNTDOWN_OPERATIONS))
def test_standalone_observer_binds_intended_child_account(monkeypatch, operation):
    monkeypatch.setattr(accessible_ui.sys, 'argv', ['observer', operation, '1.1'])
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 0)
    lookup = Mock(side_effect=LookupError('stop before connection'))
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', lookup)
    with pytest.raises(LookupError): accessible_ui.main()
    lookup.assert_called_once_with(accessible_ui.CHILD_ACCOUNTS[accessible_ui.CHILD])


@pytest.mark.parametrize('present', [True, False])
@pytest.mark.parametrize('fault', ['', 'child', 'surface', 'text', 'timestamp', 'stable', 'extra'])
def test_real_controller_decodes_countdown_and_rejects_invalid_evidence(present, fault):
    operation = 'child-countdown-present' if present else 'child-countdown-absent'
    result = value(present)
    if fault == 'child': result['child'] = 'other-child'
    if fault == 'surface': result['surface'] = 'lock'
    if fault == 'text': result['text'] = 'fixture-private-canary'
    if fault == 'timestamp': result['observed_monotonic_ns'] = True
    if fault == 'stable': result['stable_ms'] = 1
    if fault == 'extra': result['private'] = 'fixture-private-canary'
    payload = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', 'countdown': result}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(payload).encode()))
    ui = UiObservations(transport)
    if fault:
        with pytest.raises((EvidenceError, accessible_ui.UiError)): ui.observe(operation)
    else:
        decoded = ui.observe(operation)
        immutable = CountdownObservation.from_value(decoded['countdown'], present=present)
        decoded['countdown']['text'] = 'changed'
        assert immutable.text == ('00:14' if present else None)
        with pytest.raises(FrozenInstanceError): immutable.text = 'changed'


@pytest.mark.parametrize('fault', ['', 'too-high', 'too-low', 'stale', 'old', 'absent'])
def test_balance_bounds_are_independent_and_explicit(fault):
    data = value(fault != 'absent', text={'too-high': '00:16', 'too-low': '00:12'}.get(fault, '00:14'),
                 at={'stale': 10_000_000_000, 'old': 191_000_000_000}.get(fault, 20_000_000_000))
    observation = CountdownObservation.from_value(data, present=fault != 'absent')
    kwargs = dict(seconds=900, precision_seconds=1, observed_monotonic_ns=10_000_000_000)
    if fault:
        with pytest.raises(EvidenceError): check_countdown_balance(observation, **kwargs)
    else:
        assert check_countdown_balance(observation, **kwargs)['display_interval_seconds'] == [840, 899]


@pytest.mark.parametrize('fault', ['', 'balance', 'stale', 'missing', 'durability'])
def test_real_journey_step_checks_balance_before_durable_reply(tmp_path, fault):
    stage = 'independent-countdown'
    progress = Mock(side_effect=OSError('storage') if fault == 'durability' else None)
    journey = CountdownJourney(SimpleNamespace(directory=tmp_path), progress)
    journey.steps = [{'stage': name} for name in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.balance = None if fault == 'missing' else (900, 1, 10_000_000_000)
    journey.countdown = CountdownObservation.from_value(value(at=15_000_000_000), present=True)
    result = value(text='00:16' if fault == 'balance' else '00:14',
                   at=15_000_000_000 if fault == 'stale' else 20_000_000_000)
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': 'child-countdown-present', 'outcome': 'passed', 'countdown': result}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert json.loads((tmp_path / (stage + '.reply.json')).read_text()) == {'observed': stage}
        assert journey.steps[-1]['comparison']['sampling_seconds'] == 2
        progress.assert_called_once()


@pytest.mark.parametrize('fail_first', [False, True])
def test_fixed_qualification_uses_separate_attempts_and_stops_on_failure(monkeypatch, fail_first):
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kw: calls.append(kw) or (1 if fail_first else 0))
    assert check.main() == (1 if fail_first else 0)
    assert [call['challenge_profile'] for call in calls] == (
        ['countdown-enabled'] if fail_first else ['countdown-enabled', 'countdown-off'])
    for cls, expected_plan in ((CountdownQualification, PLAN), (CountdownOffQualification, OFF_PLAN)):
        context = SimpleNamespace()
        q = object.__new__(cls)
        journey = q.journey(context, Mock())
        assert journey.plan is expected_plan and context.installed_snapshot.startswith('onpc-v')
        for operation in expected_plan.screen_tags.values():
            if operation.startswith('ui:'): assert operation[3:] in accessible_ui.OPERATIONS


def animation_tree(monkeypatch):
    ui, root, shell, _, indicator, _, _ = tree(monkeypatch)
    toggle = Node(identity='child-countdown-animation-toggle', role='check box', value=False)
    toggle.ui_element = SimpleNamespace()
    menu = Node(identity='child-countdown-menu')
    menu.ui_element = SimpleNamespace()
    menu.activate = Mock()
    for node in (toggle, menu):
        node.parent = indicator
        indicator.children.append(node)
    return ui, root, shell, indicator, toggle, menu


@pytest.mark.parametrize('desired', [True, False])
def test_panel_animation_canonical_input_and_independent_read_without_menu(monkeypatch, desired):
    ui, _, _, _, toggle, menu = animation_tree(monkeypatch)
    toggle._set_value(not desired)
    result = ui.run('child-countdown-animation-' + ('on' if desired else 'off'), '')
    assert result['panel_animation']['animation'] is desired
    toggle.setValue.assert_called_once_with(desired)
    assert ui.run('child-countdown-animation-read', '')['panel_animation']['animation'] is desired
    ui.run('child-countdown-animation-' + ('on' if desired else 'off'), '')
    toggle.setValue.assert_called_once_with(desired)
    menu.activate.assert_not_called()
    toggle.action.do_action.assert_not_called()
    toggle.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-account', 'inactive', 'wrong-owner', 'duplicate',
    'hidden', 'disabled', 'prompt', 'defunct', 'incomplete', 'uncertain'])
def test_panel_animation_guard_refusal_preserves_single_input(monkeypatch, fault):
    ui, _, shell, indicator, toggle, menu = animation_tree(monkeypatch)
    if fault == 'wrong-account':
        monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 1002)
        ui.read_snapshot = Mock(side_effect=AssertionError('discovery before identity refusal'))
    if fault == 'inactive':
        accessible_ui.require_active_launch_session.side_effect = accessible_ui.UiError('ui:launch-session')
    if fault == 'wrong-owner': shell.identity = 'foreign-app'
    if fault == 'duplicate': indicator.children.append(Node(identity=toggle.identity))
    if fault == 'hidden': toggle.states.discard('visible')
    if fault == 'disabled': toggle.states.discard('sensitive')
    if fault == 'prompt': ui.system_prompt_kind = Mock(return_value='keyring')
    if fault == 'defunct': toggle.states.add('defunct')
    if fault == 'incomplete': shell.children.append(None)
    if fault == 'uncertain': toggle.setValue.side_effect = TimeoutError()
    with pytest.raises((accessible_ui.UiError, TimeoutError)):
        ui.run('child-countdown-animation-on', '')
    assert toggle.setValue.call_count == (1 if fault == 'uncertain' else 0)
    if fault == 'uncertain':
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.run('child-countdown-animation-on', '')
        toggle.setValue.assert_called_once()
    if fault == 'wrong-account':
        assert ui.run('child-countdown-animation-wrong-account-refused', '')['refused'] is True
        ui.read_snapshot.assert_not_called()
    menu.activate.assert_not_called()


def test_panel_animation_invalid_argument_and_menu_entry_share_guards(monkeypatch):
    ui, _, _, _, toggle, menu = animation_tree(monkeypatch)
    with pytest.raises(accessible_ui.UiError, match='panel-animation-binding'):
        ui.child_countdown_animation(1)
    toggle.setValue.assert_not_called()
    ui.child_countdown_menu()
    menu.activate.assert_called_once_with()
    monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 1002)
    ui.read_snapshot = Mock(side_effect=AssertionError('unavailable discovery'))
    with pytest.raises(accessible_ui.UiError, match='overlay-account'):
        ui.child_countdown_menu()
    menu.activate.assert_called_once()
    ui.read_snapshot.assert_not_called()


@pytest.mark.parametrize('operation', sorted(accessible_ui.PANEL_ANIMATION_OPERATIONS))
def test_panel_animation_observer_binds_child_account_before_connection(monkeypatch, operation):
    monkeypatch.setattr(accessible_ui.sys, 'argv', ['observer', operation, '1.1'])
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 0)
    lookup = Mock(side_effect=LookupError('stop before connection'))
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', lookup)
    with pytest.raises(LookupError): accessible_ui.main()
    lookup.assert_called_once_with(accessible_ui.CHILD_ACCOUNTS[accessible_ui.CHILD])


@pytest.mark.parametrize('fault', ['', 'child', 'surface', 'value', 'timestamp', 'extra', 'wrong-result'])
def test_panel_animation_real_decoder_refuses_malformed_or_wrong_result(fault):
    value = {'child': 'fixture-child', 'surface': 'desktop', 'animation': True,
             'observed_monotonic_ns': 20_000_000_000}
    if fault == 'child': value['child'] = 'other-child'
    if fault == 'surface': value['surface'] = 'lock'
    if fault == 'value': value['animation'] = 1
    if fault == 'timestamp': value['observed_monotonic_ns'] = True
    if fault == 'extra': value['private'] = 'canary'
    if fault == 'wrong-result': value['animation'] = False
    payload = {'operation': 'child-countdown-animation-on', 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'panel_animation': value}
    observer = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(payload).encode())))
    if fault:
        with pytest.raises((EvidenceError, accessible_ui.UiError)):
            observer.observe(payload['operation'])
    else:
        assert observer.observe(payload['operation'])['panel_animation'] == value


@pytest.mark.parametrize('fault', ['', 'off', 'stale', 'missing', 'durability'])
def test_panel_animation_real_step_refuses_before_durable_reply(tmp_path, fault):
    stage = 'animation-read'
    journey = CountdownAnimationJourney(SimpleNamespace(directory=tmp_path),
        Mock(side_effect=OSError('storage') if fault == 'durability' else None))
    journey.steps = [{'stage': name} for name in ANIMATION_PLAN.stages[:ANIMATION_PLAN.stages.index(stage)]]
    journey.animation_observed_ns = None if fault == 'missing' else 10_000_000_000
    result = {'child': 'fixture-child', 'surface': 'desktop', 'animation': fault != 'off',
              'observed_monotonic_ns': 10_000_000_000 if fault == 'stale' else 20_000_000_000}
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value={
        'operation': 'child-countdown-animation-read', 'outcome': 'passed', 'panel_animation': result}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert json.loads((tmp_path / (stage + '.reply.json')).read_text()) == {'observed': stage}


def test_panel_animation_selector_uses_current_inputs_and_real_constructor(monkeypatch, tmp_path):
    from tools.test_storage import named_input
    from tools.test_commands import qualification_input_options
    from tests.support.paths import ROOT
    calls = []
    monkeypatch.setattr(animation_check, 'smoke', lambda **kw: calls.append(kw) or 0)
    assert animation_check.main() == 0
    assert calls == [{'assets': named_input(), 'provision_credentials': True,
        'challenges': True, 'challenge_profile': 'countdown-animation'}]
    assert qualification_input_options(ROOT, 'check_e2e_operate_the_countdown_context_menu') == {}
    context = SimpleNamespace()
    journey = CountdownAnimationQualification.journey(context, Mock())
    assert journey.plan is ANIMATION_PLAN and context.installed_snapshot.startswith('onpc-v')
    for operation in ANIMATION_PLAN.screen_tags.values():
        if operation.startswith('ui:'): assert operation[3:] in accessible_ui.OPERATIONS
    from installed_journey import record_installed_journey
    from unittest.mock import MagicMock
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock(), recorder=MagicMock())
    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is CountdownAnimationJourney and controller.plan is ANIMATION_PLAN
        assert controller.actions == {}
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = worker
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(context.recorder, context, ANIMATION_PLAN,
            journey_type=CountdownAnimationJourney, actions={})


def sample(text='00:03', *, start=100, end=101, guest=10, boot='b' * 64):
    return sampling.CountdownSample.from_ui({'countdown': value(text=text, at=guest * 1_000_000_000),
        'countdown_read_bounds': [int(start * 1_000_000_000), int(end * 1_000_000_000)]},
        boot_sha256=boot)


@pytest.mark.parametrize('text,start,end,guest,boot,error', [
    ('00:02', 160, 161, 70, 'b' * 64, None),
    ('00:02', 101.1, 102, 11, 'b' * 64, None),  # A real minute edge need not take 60 s.
    ('00:01', 220, 221, 130, 'b' * 64, None),  # A skipped intermediate tick is fine.
    ('00:02', 158, 162, 70, 'b' * 64, None),  # Read latency is an interval.
    ('00:03', 160, 161, 70, 'b' * 64, 'no-progress'),
    ('00:04', 160, 161, 70, 'b' * 64, 'no-progress'),
    ('00:01', 101.1, 102, 11, 'b' * 64, 'progress-mismatch'),
    ('00:02', 100, 101, 70, 'b' * 64, 'stale-sample'),
    ('00:02', 160, 161, 10, 'b' * 64, 'stale-sample'),
    ('00:02', 160, 161, 70, 'a' * 64, 'wrong-owner'),
    ('00:02', 401, 402, 310, 'b' * 64, 'progress-bound'),
    ('60', 160, 161, 70, 'b' * 64, 'minute-required'),
])
def test_successive_samples_require_independent_progress(text, start, end, guest, boot, error):
    previous = sample()
    current = sample(text, start=start, end=end, guest=guest, boot=boot)
    kwargs = dict(precision_seconds=60, tolerance_seconds=2, max_elapsed_seconds=300)
    if error:
        with pytest.raises(EvidenceError, match='countdown:' + error):
            sampling.check_countdown_progress(current, previous, **kwargs)
    else:
        result = sampling.check_countdown_progress(current, previous, **kwargs)
        assert result['elapsed_interval_seconds'] == pytest.approx([start - 101, end - 100])
        assert result['precision_seconds'] == 60
    assert previous.countdown.text == '00:03' and previous.read_bounds == (100_000_000_000, 101_000_000_000)
    with pytest.raises(FrozenInstanceError): previous.read_bounds = ()


@pytest.mark.parametrize('fault', ['precision', 'tolerance', 'bound', 'reversed', 'owner', 'child'])
def test_sample_or_progress_binding_refuses_before_wait_or_read(fault):
    kwargs = dict(precision_seconds=60, tolerance_seconds=2, max_elapsed_seconds=90)
    if fault == 'precision': kwargs['precision_seconds'] = 2
    if fault == 'tolerance': kwargs['tolerance_seconds'] = 3
    if fault == 'bound': kwargs['max_elapsed_seconds'] = True
    guard = Mock()
    ui = Mock()
    if fault in ('reversed', 'owner', 'child'):
        data = {'countdown': value(text='00:03'), 'countdown_read_bounds': [101, 100] if fault == 'reversed' else [100, 101]}
        if fault == 'child': data['countdown']['child'] = 'other-child'
        with pytest.raises((EvidenceError, accessible_ui.UiError)):
            sampling.CountdownSample.from_ui(data, boot_sha256='bad' if fault == 'owner' else 'b' * 64)
    else:
        with pytest.raises(EvidenceError, match='progress-binding'):
            sampling.await_countdown_progress(SimpleNamespace(ui=ui), guard, sample(), **kwargs)
    guard.assert_not_called()
    ui.observe.assert_not_called()


@pytest.fixture
def minute_clock(monkeypatch):
    now = [101.0]
    monkeypatch.setattr(sampling.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(sampling.time, 'monotonic_ns', lambda: int(now[0] * 1_000_000_000))
    monkeypatch.setattr(sampling.time, 'sleep', lambda delay: now.__setitem__(0, now[0] + delay))
    return now


def minute_observer(now, *, fault=None):
    ui = SimpleNamespace(boot_proof='b' * 64)
    def observe(_):
        started = now[0]
        now[0] += .1
        text = '00:03' if now[0] < 104 or fault == 'stall' else '00:02'
        result = {'countdown': value(text=text, at=int(now[0] * 1_000_000_000)),
                  'countdown_read_bounds': [int(started * 1_000_000_000), int(now[0] * 1_000_000_000)]}
        if fault == 'owner': ui.boot_proof = 'a' * 64
        if fault == 'stale': result['countdown']['observed_monotonic_ns'] = 10_000_000_000
        if fault == 'late': now[0] = 191
        if fault == 'child': result['countdown']['child'] = 'other-child'
        return result
    ui.observe = Mock(side_effect=observe)
    return ui


@pytest.mark.parametrize('fault', [None, 'stall', 'owner', 'stale', 'late', 'child', 'guard', 'cancel'])
def test_guarded_reacquisition_progress_and_stall_bound(minute_clock, fault):
    ui = minute_observer(minute_clock, fault=fault)
    journey = SimpleNamespace(ui=ui, watch_progress=None)
    def guard():
        if minute_clock[0] > 102 and fault in ('guard', 'cancel'):
            raise RuntimeError('lost-owner') if fault == 'guard' else KeyboardInterrupt()
        return 1000
    if fault:
        with pytest.raises((EvidenceError, accessible_ui.UiError, RuntimeError, KeyboardInterrupt)):
            sampling.await_countdown_progress(journey, guard, sample(), precision_seconds=60,
                tolerance_seconds=2, max_elapsed_seconds=90)
        assert minute_clock[0] <= 191
    else:
        current, result = sampling.await_countdown_progress(journey, guard, sample(),
            precision_seconds=60, tolerance_seconds=2, max_elapsed_seconds=90)
        assert current.countdown.text == '00:02' and ui.observe.call_count == 3
        assert set(result) == {'before', 'after', 'comparison'}
        assert result['before']['countdown']['text'] == '00:03'


def test_controller_brackets_each_read_independently(monkeypatch):
    ui = UiObservations(Mock(call=Mock(return_value=json.dumps({
        'operation': 'child-countdown-present', 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'countdown': value()}).encode())))
    times = iter((100, 110, 120, 135))
    monkeypatch.setattr(sampling.time, 'monotonic_ns', lambda: next(times))
    first = ui.observe('child-countdown-present')
    second = ui.observe('child-countdown-present')
    assert first['countdown_read_bounds'] == [100, 110]
    assert second['countdown_read_bounds'] == [120, 135]


@pytest.mark.parametrize('fault', [None, 'stall', 'owner', 'stale', 'durability'])
def test_minute_journey_actual_step_no_reply_after_failed_progress(tmp_path, minute_clock, fault):
    from countdown_qualification import CountdownMinutesJourney, MINUTE_PLAN
    stage = 'minute-progression'
    progress = Mock(side_effect=OSError('storage') if fault == 'durability' else None)
    journey = CountdownMinutesJourney(SimpleNamespace(directory=tmp_path), progress)
    journey.steps = [{'stage': name} for name in MINUTE_PLAN.stages[:MINUTE_PLAN.stages.index(stage)]]
    journey.balance = (240, 1, 1_000_000_000)
    journey.ui = minute_observer(minute_clock, fault=fault)
    journey.ui.observe.side_effect = [
        {'countdown': value(text='00:03', at=10_000_000_000),
         'countdown_read_bounds': [100_000_000_000, 101_000_000_000]},
        *([{'countdown': value(text='00:03' if fault == 'stall' else '00:02',
            at=10_000_000_000 if fault == 'stale' else (12 + i) * 1_000_000_000),
            'countdown_read_bounds': [(102 + i) * 1_000_000_000, (102 + i) * 1_000_000_000]}
           for i in range(100)])]
    if fault == 'owner': journey.boot = 'a' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            journey.step(lambda: 1000)
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(lambda: 1000)
    else:
        journey.step(lambda: 1000)
        assert journey.steps[-1]['fixture']['comparison']['precision_seconds'] == 60
        assert journey.last_countdown.countdown.text == '00:02'
        assert (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('seconds', [False, True], ids=['minutes', 'final-seconds'])
def test_progress_selector_and_real_recorder_constructor(monkeypatch, tmp_path, seconds):
    import check_e2e_countdown_minutes
    import check_e2e_countdown_ticks
    from countdown_qualification import CountdownMinutesJourney, MINUTE_PLAN, CountdownTicksJourney, TICK_PLAN
    from parent_setup_qualification import CountdownMinutesQualification, CountdownTicksQualification
    selector, kind, plan, qualification, profile = (
        (check_e2e_countdown_ticks, CountdownTicksJourney, TICK_PLAN,
         CountdownTicksQualification, 'countdown-ticks') if seconds else
        (check_e2e_countdown_minutes, CountdownMinutesJourney, MINUTE_PLAN,
         CountdownMinutesQualification, 'countdown-minutes'))
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0 and run.call_args.kwargs['challenge_profile'] == profile
    with pytest.raises(CommandError, match='challenges-prerequisites'):
        smoke.main(challenges=True, challenge_profile=profile)
    context = SimpleNamespace(directory=tmp_path)
    assert qualification.journey(context, Mock()).plan is plan
    assert context.installed_snapshot.startswith('onpc-v')
    # Real entry point passes plan/actions to this subclass before worker startup.
    from installed_journey import record_installed_journey
    from unittest.mock import MagicMock
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock(), recorder=MagicMock())
    def worker(**options):
        controller = options['guarded_observe'].__self__
        assert type(controller) is kind and controller.plan is plan
        assert set(controller.actions) == set(plan.stage_actions.values())
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = worker
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(context.recorder, context, plan, journey_type=kind)


@pytest.mark.parametrize('fault', [None, 'reversed', 'stale', 'owner'])
def test_independent_minute_entry_cannot_reseed_reversed_or_stale_endpoints(tmp_path, fault):
    from countdown_qualification import CountdownMinutesJourney
    journey = CountdownMinutesJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.last_countdown = sample('00:02')
    current = sample('00:03' if fault == 'reversed' else '00:02',
        start=100 if fault == 'stale' else 102, end=103, guest=12,
        boot='a' * 64 if fault == 'owner' else 'b' * 64)
    observed = {'boot_sha256': current.boot_sha256, 'ui': {
        'countdown': value(text=current.countdown.text, at=current.countdown.observed_monotonic_ns),
        'countdown_read_bounds': current.read_bounds}}
    if fault:
        with pytest.raises(EvidenceError):
            journey.check_settings('independent-minute-progression', observed)
        assert journey.current_countdown is None
    else:
        journey.check_settings('independent-minute-progression', observed)
        assert journey.current_countdown == current
    assert journey.last_countdown.countdown.text == '00:02'


@pytest.mark.parametrize('seconds', [False, True], ids=['minutes', 'final-seconds'])
def test_actual_progress_worker_order_titles_and_every_refusal(monkeypatch, seconds):
    from countdown_qualification import MINUTE_PLAN, TICK_PLAN
    plan = TICK_PLAN if seconds else MINUTE_PLAN
    script = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_password.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['title', $_[0]]; }
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
 die 'fixture:refused' if $_[0] eq $ENV{ONPC_TEST_REFUSE};
 return {observed => $_[0], ui_focused => JSON::PP::true};
};
my $ok = eval { onpc_challenges::countdown_minutes($exchange, $plan->{invocations}, $plan->{challenges}); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''
    if seconds:
        script = script.replace('onpc_challenges::countdown_minutes(', 'onpc_challenges::countdown_ticks(')
    args = json.dumps({'invocations': plan.invocations, 'challenges': plan.challenges})
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script, args).stdout)
    assert success['ok'], success['error']
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == list(plan.screen_tags)
    assert [event[1] for event in success['events'] if event[0] == 'title'] == [
        *(plan.prefix + '-' + stage for stage in plan.screen_tags), 'shutdown']
    for stage in plan.screen_tags:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script, args).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        assert result['events'] == success['events'][:success['events'].index(['stage', stage]) + 1]
    for tag in plan.screen_tags.values():
        if tag.startswith('ui:'): assert tag[3:] in accessible_ui.OPERATIONS


@pytest.mark.parametrize('before,after,start,end,previous_precision,error', [
    ('60', '55', 105, 106, 1, None),
    ('60', '54', 104, 107, 1, None),  # Read latency, not callback timing.
    ('60', '59', 101.1, 102, 1, None),
    ('00:01', '60', 150, 151, 60, None),
    ('00:01', '58', 160, 161, 60, None),
    ('60', '60', 105, 106, 1, 'no-progress'),
    ('55', '60', 105, 106, 1, 'no-progress'),
    ('60', '40', 105, 106, 1, 'progress-mismatch'),
    ('60', '59', 120, 121, 1, 'progress-mismatch'),
    ('00:01', '60', 105, 106, 1, 'seconds-required'),
    ('60', '00:01', 105, 106, 1, 'seconds-required'),
])
def test_exact_final_seconds_and_explicit_transition(before, after, start, end,
                                                      previous_precision, error):
    previous, current = sample(before), sample(after, start=start, end=end, guest=20)
    options = dict(precision_seconds=1, previous_precision_seconds=previous_precision,
                   tolerance_seconds=2, max_elapsed_seconds=90)
    if error:
        with pytest.raises(EvidenceError, match=error):
            sampling.check_countdown_progress(current, previous, **options)
    else:
        result = sampling.check_countdown_progress(current, previous, **options)
        assert result['precision_seconds'] == 1
        assert result['previous_precision_seconds'] == previous_precision
        if previous_precision == 1:
            assert result['decrease_interval_seconds'] == [int(before) - int(after)] * 2


@pytest.mark.parametrize('fault', [None, 'stall', 'reversed', 'stale', 'owner', 'late', 'guard'])
def test_final_seconds_guarded_sampling_keeps_original_bound(minute_clock, fault):
    previous = sample('60')
    def observe(_):
        start = minute_clock[0]
        minute_clock[0] += .1
        text = '60' if fault == 'stall' else '58' if start < 103 else '56'
        if fault == 'reversed': text = '00:01'
        if fault == 'late': minute_clock[0] = 116
        return {'countdown': value(text=text, at=10_000_000_000 if fault == 'stale'
                                  else int(minute_clock[0] * 1_000_000_000)),
                'countdown_read_bounds': [int(start * 1_000_000_000),
                                         int(minute_clock[0] * 1_000_000_000)]}
    ui = SimpleNamespace(boot_proof=('a' if fault == 'owner' else 'b') * 64,
                         observe=Mock(side_effect=observe))
    journey = SimpleNamespace(ui=ui, watch_progress=None)
    guard = Mock(return_value=1000, side_effect=RuntimeError('lost-owner') if fault == 'guard' else None)
    if fault:
        with pytest.raises((EvidenceError, RuntimeError)):
            sampling.await_countdown_progress(journey, guard, previous, precision_seconds=1,
                tolerance_seconds=2, max_elapsed_seconds=15)
        assert minute_clock[0] <= 116
    else:
        current, result = sampling.await_countdown_progress(journey, guard, previous,
            precision_seconds=1, tolerance_seconds=2, max_elapsed_seconds=15)
        assert current.countdown.text == '58'
        assert result['before']['countdown']['text'] == '60'


def test_transition_wait_skips_unchanged_minute_reads_without_restarting(minute_clock):
    previous = sample('00:01')
    reads = iter(('00:01', '00:01', '60'))
    def observe(_):
        start = minute_clock[0]
        minute_clock[0] += .1
        return {'countdown': value(text=next(reads), at=int(minute_clock[0] * 1_000_000_000)),
                'countdown_read_bounds': [int(start * 1_000_000_000),
                                         int(minute_clock[0] * 1_000_000_000)]}
    journey = SimpleNamespace(ui=SimpleNamespace(boot_proof='b' * 64, observe=Mock(side_effect=observe)),
                              watch_progress=None)
    current, result = sampling.await_countdown_progress(journey, lambda: 1000, previous,
        precision_seconds=1, previous_precision_seconds=60, tolerance_seconds=2,
        max_elapsed_seconds=90)
    assert current.countdown.text == '60'
    assert result['before']['read_bounds'] == previous.read_bounds
    assert journey.ui.observe.call_count == 3


@pytest.mark.parametrize('fault', [None, 'window', 'reversed', 'stale', 'owner', 'stall', 'durability'])
def test_final_journey_real_step_refuses_before_reply_and_keeps_endpoint(tmp_path, minute_clock, fault):
    from countdown_qualification import CountdownTicksJourney, TICK_PLAN
    minute_clock[0] = 102.0  # The next read must start after the original read ends.
    stage = 'independent-second-progression'
    progress = Mock(side_effect=OSError('storage') if fault == 'durability' else None)
    journey = CountdownTicksJourney(SimpleNamespace(directory=tmp_path), progress)
    journey.steps = [{'stage': name} for name in TICK_PLAN.stages[:TICK_PLAN.stages.index(stage)]]
    original = sample('60')
    journey.last_countdown = original
    def observe(_):
        start = minute_clock[0]
        minute_clock[0] += .1
        if fault == 'window': minute_clock[0] = 116
        text = '00:01' if fault == 'reversed' else '60' if fault == 'stall' else '58'
        return {'countdown': value(text=text, at=10_000_000_000 if fault == 'stale'
                                  else int(minute_clock[0] * 1_000_000_000)),
                'countdown_read_bounds': [int(start * 1_000_000_000),
                                         int(minute_clock[0] * 1_000_000_000)]}
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(side_effect=observe))
    if fault == 'owner': journey.boot = 'a' * 64
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        error = {'window': 'progress-bound', 'reversed': 'seconds-required',
                 'stale': 'stale-sample', 'owner': 'boot', 'stall': 'progress-bound',
                 'durability': 'storage'}[fault]
        with pytest.raises((EvidenceError, OSError), match=error):
            journey.step(lambda: 1000)
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(lambda: 1000)
    else:
        journey.step(lambda: 1000)
        result = journey.steps[-1]['fixture']
        assert result['before']['read_bounds'] == original.read_bounds
        assert result['comparison']['decrease_interval_seconds'] == [2, 2]
        assert journey.steps[-1]['assertion']['id'] == stage
        assert (tmp_path / (stage + '.reply.json')).exists()
    assert original.countdown.text == '60'


@pytest.mark.parametrize('text', ['00:02', '60', '0'])
def test_initial_transition_window_cannot_be_repaired_with_a_fresh_allowance(tmp_path, text):
    from countdown_qualification import CountdownTicksJourney
    journey = CountdownTicksJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='transition-window'):
        journey.check_progress_entry(sample(text))
    assert journey.last_countdown is None and journey.current_countdown is None


@pytest.mark.parametrize('fault', [None, 'stale', 'owner', 'late'])
def test_independent_initial_sample_preserves_original_deadline_and_refusal(minute_clock, fault):
    previous = sample('60')
    current = sample('58', start=101 if fault == 'stale' else 102,
                     end=116 if fault == 'late' else 103, guest=20,
                     boot=('a' if fault == 'owner' else 'b') * 64)
    minute_clock[0] = 116 if fault == 'late' else 103
    journey = SimpleNamespace(ui=SimpleNamespace(boot_proof='b' * 64, observe=Mock()),
                              watch_progress=None)
    options = dict(precision_seconds=1, tolerance_seconds=2, max_elapsed_seconds=15,
                   initial_sample=current)
    if fault:
        with pytest.raises(EvidenceError, match={'stale': 'stale-sample', 'owner': 'wrong-owner',
                                                 'late': 'progress-bound'}[fault]):
            sampling.await_countdown_progress(journey, lambda: 1000, previous, **options)
    else:
        endpoint, result = sampling.await_countdown_progress(journey, lambda: 1000, previous, **options)
        assert endpoint is current and result['before']['read_bounds'] == previous.read_bounds
    journey.ui.observe.assert_not_called()
