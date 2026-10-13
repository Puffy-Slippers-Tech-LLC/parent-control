"""TIME04 safety with synthetic clocks, public node doubles and memory transport.

These checks establish harness refusals, never installed expiry acceptance.
"""

from dataclasses import asdict
import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from countdown import CountdownObservation, CountdownSample
import natural_expiry_observation as expiry
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import AppActivityObservation, UiObservations


BOOT, SESSION, SOURCE, SURFACE = (letter * 64 for letter in 'bcde')
OBSERVE = 'child-natural-expiry-observe'
ACTIVITY = 'child-natural-expiry-activity'
READY = 'child-natural-expiry-lock-ready'
RESULT = 'child-natural-expiry-lock-result'


def activity_value():
    return {'binding': 'native-primary', 'pid': 100,
            'endpoint': [':1.7', '/fixture/window'],
            'state': {'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft',
                      'score': 'Moves: 0; token: 0'}}


def lock_value():
    return {'entry': 'curtain', 'owner': 'fixture-child', 'locked': True,
            'desktop_input_available': False, 'recipient': None, 'surface_id': SURFACE,
            'provider': {'version': '50', 'locale': 'en_US.UTF-8',
                         'keyboard': [['xkb', 'us']]}}


def observation(*, locked=False, acted=False, seconds=20):
    return {'state': 'locked' if locked else 'desktop', 'session_sha256': SESSION,
            'source': None if locked else SOURCE,
            'activity': None if locked else activity_value(),
            'seconds': None if locked else seconds,
            'lock': lock_value() if locked else None, 'acted': acted}


@pytest.fixture
def clock(monkeypatch):
    now = [101.0]
    monkeypatch.setattr(expiry, 'time', SimpleNamespace(
        monotonic=lambda: now[0], monotonic_ns=lambda: round(now[0] * 1e9)))
    def interval(seconds):
        def advance(_journey, guard):
            guard()
            now[0] += seconds
        return advance
    monkeypatch.setattr(expiry, 'interval_action', interval)
    return now


def sample():
    return CountdownSample(CountdownObservation(True, '20', 10_000_000_000, 0),
                           (100_000_000_000, 101_000_000_000), BOOT)


def helper_journey(clock, readings):
    ui = SimpleNamespace(boot_proof=BOOT)
    pending = iter(readings)
    def read(_operation):
        at, value = next(pending)
        clock[0] = at
        return {'natural_expiry': value}
    ui.observe = Mock(side_effect=read)
    return SimpleNamespace(ui=ui)


def test_activity_then_independent_lock_preserves_initial_sample_and_elapsed_bounds(clock):
    original = sample()
    journey = helper_journey(clock, [(101.1, observation()),
        (103.0, observation(acted=True)), (120.5, observation(locked=True))])
    result = expiry.await_natural_expiry(journey, lambda: 1000, original,
        AppActivityObservation.from_value(activity_value()))
    assert result['initial_countdown'] == asdict(original)
    assert result['lock'] == lock_value() and result['activity_actions'] == 1
    assert result['elapsed_interval_seconds'] == [3.0, 20.5]
    assert [call.args[0] for call in journey.ui.observe.call_args_list] == [
        OBSERVE, ACTIVITY, ACTIVITY]


@pytest.mark.parametrize('fault', ['premature', 'late', 'no-activity', 'boot', 'session', 'app'])
def test_natural_lock_requires_timely_same_session_activity(clock, fault):
    second = observation(locked=True, acted=fault != 'no-activity')
    at = 105 if fault == 'premature' else 136 if fault == 'late' else 120
    if fault == 'session':
        second['session_sha256'] = 'f' * 64
    if fault == 'app':
        second = observation(acted=True)
        second['activity']['pid'] = 101
    journey = helper_journey(clock, [(101.1, observation()), (at, second)])
    if fault == 'boot':
        journey.ui.boot_proof = 'f' * 64
    with pytest.raises(EvidenceError):
        expiry.await_natural_expiry(journey, lambda: 1000, sample(),
            AppActivityObservation.from_value(activity_value()))
    assert journey.ui.observe.call_count <= 2


@pytest.mark.parametrize('attempt_deadline', [1000, 134])
def test_stalled_desktop_does_not_extend_original_or_attempt_deadline(clock, attempt_deadline):
    journey = SimpleNamespace(ui=SimpleNamespace(boot_proof=BOOT))
    read_starts = []
    def stalled(_operation):
        read_starts.append(clock[0])
        clock[0] += .1
        return {'natural_expiry': observation(acted=_operation == ACTIVITY)}
    journey.ui.observe = Mock(side_effect=stalled)
    with pytest.raises(EvidenceError, match='deadline'):
        expiry.await_natural_expiry(journey, lambda: attempt_deadline, sample(),
            AppActivityObservation.from_value(activity_value()))
    assert all(start < min(135, attempt_deadline) for start in read_starts)
    # A read that began in time may complete after the deadline, but cannot
    # produce an accepted result or authorize another read.
    assert clock[0] <= min(135, attempt_deadline) + .100001
    assert journey.ui.observe.call_count < 35


def adapter():
    """Keep activity reads synthetic; exercise the real guarded input dispatch."""
    submit = Node(identity='onpc-fixture-native-primary-submit')
    window = Node(identity='onpc-fixture-native-primary', children=[submit])
    window.bus, window.path = ':1.7', '/fixture/window'
    remaining = Node(identity='child-remaining-time', value=20)
    ui = ui_for(Node(children=[window, remaining]))
    ui.natural_expiry_session = Mock(return_value=(SESSION, False))
    ui.native_app_snapshot = Mock(return_value=activity_value())
    ui._lock_surface = Mock(return_value=lock_value())
    ui.snapshot_owned_target = Mock(side_effect=lambda identity, **_kwargs: {
        window.identity: window, submit.identity: submit, remaining.identity: remaining}[identity])
    ui.expected_natural_expiry_source = hashlib.sha256(json.dumps(
        [SESSION, 100, [':1.7', '/fixture/window']], sort_keys=True).encode()).hexdigest()
    in_wait = [False]
    def wait(predicate, *_args, **_kwargs):
        in_wait[0] = True
        try:
            for _ in range(4):
                try:
                    value = predicate()
                except accessible_ui.UiError as error:
                    if str(error) != 'ui:incomplete-tree':
                        raise
                    continue
                if value is not None:
                    return value
            raise AssertionError('read-only wait never produced a complete result')
        finally:
            in_wait[0] = False
    ui.wait = Mock(side_effect=wait)
    return ui, window, submit, remaining, in_wait


@pytest.mark.parametrize('fault', ['wrong-owner', 'stale-source', 'uncertain', 'locked',
                                   'wrong-session', 'near-zero'])
def test_refused_or_locked_activity_releases_no_app_input(fault):
    ui, window, submit, remaining, _ = adapter()
    if fault == 'wrong-owner':
        window.get_process_id = Mock(return_value=999)
    elif fault == 'stale-source':
        ui.expected_natural_expiry_source = 'a' * 64
    elif fault == 'uncertain':
        ui.input_uncertain = True
    elif fault == 'locked':
        ui.natural_expiry_session.return_value = (SESSION, True)
    elif fault == 'wrong-session':
        ui.natural_expiry_session.side_effect = [(SESSION, False), ('f' * 64, False)]
    elif fault == 'near-zero':
        remaining.value = 10
    if fault in ('locked', 'near-zero'):
        assert ui.natural_expiry(ACTIVITY)['acted'] is False
    else:
        with pytest.raises(accessible_ui.UiError):
            ui.natural_expiry(ACTIVITY)
    submit.action.do_action.assert_not_called()
    submit.component.grab_focus.assert_not_called()
    if fault in ('locked', 'uncertain'):
        ui.native_app_snapshot.assert_not_called()
        ui.snapshot_owned_target.assert_not_called()


def test_stale_source_failure_is_not_hidden_by_racing_lock():
    ui, _, submit, _, _ = adapter()
    ui.expected_natural_expiry_source = 'a' * 64
    ui.natural_expiry_session.side_effect = [(SESSION, False), (SESSION, False), (SESSION, True)]
    with pytest.raises(accessible_ui.UiError, match='stale-activity'):
        ui.natural_expiry(ACTIVITY)
    submit.action.do_action.assert_not_called()
    ui._lock_surface.assert_not_called()


def test_wrong_owner_failure_is_not_hidden_by_racing_lock():
    ui, _, submit, _, _ = adapter()
    ui.native_app_snapshot.side_effect = accessible_ui.UiError('ui:wrong-owner')
    ui.natural_expiry_session.side_effect = [(SESSION, False), (SESSION, False), (SESSION, True)]
    with pytest.raises(accessible_ui.UiError, match='wrong-owner'):
        ui.natural_expiry(ACTIVITY)
    submit.action.do_action.assert_not_called()
    ui._lock_surface.assert_not_called()


def test_wrong_child_account_refuses_before_session_or_app_discovery(monkeypatch):
    ui, _, submit, _, _ = adapter()
    ui.natural_expiry_session = accessible_ui.AccessibleUI.natural_expiry_session.__get__(ui)
    monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 1002)
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 1002)
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1001))
    discovery = Mock(side_effect=AssertionError('session service unavailable'))
    monkeypatch.setattr(accessible_ui.session_control, 'sessions', discovery)
    with pytest.raises(accessible_ui.UiError, match='natural-expiry-account'):
        ui.natural_expiry(ACTIVITY)
    discovery.assert_not_called()
    ui.native_app_snapshot.assert_not_called()
    ui.snapshot_owned_target.assert_not_called()
    submit.action.do_action.assert_not_called()


def test_wrong_account_refusal_route_binds_parent_and_uses_real_entry_guard(monkeypatch):
    operation = 'child-natural-expiry-wrong-account-refused'
    ui, _, submit, _, _ = adapter()
    ui.natural_expiry_session = accessible_ui.AccessibleUI.natural_expiry_session.__get__(ui)
    ui.natural_expiry = Mock(wraps=ui.natural_expiry)
    monkeypatch.setattr(accessible_ui.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1001))
    discovery = Mock(side_effect=AssertionError('session service unavailable'))
    monkeypatch.setattr(accessible_ui.session_control, 'sessions', discovery)
    ui.read_snapshot = Mock(side_effect=AssertionError('provider discovery unavailable'))
    assert ui.run(operation, '') == {'operation': operation, 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'natural_expiry_refused': True}
    ui.natural_expiry.assert_called_once_with(OBSERVE)
    discovery.assert_not_called()
    ui.read_snapshot.assert_not_called()
    ui.native_app_snapshot.assert_not_called()
    ui.snapshot_owned_target.assert_not_called()
    submit.action.do_action.assert_not_called()

    # Stop at the selected account lookup, before any connection or setuid.
    monkeypatch.setattr(accessible_ui.sys, 'argv', ['observer', operation, '1.1'])
    monkeypatch.setattr(accessible_ui.os, 'geteuid', lambda: 0)
    account = Mock(side_effect=LookupError('stop at account binding'))
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', account)
    with pytest.raises(LookupError, match='stop at account binding'):
        accessible_ui.main()
    account.assert_called_once_with('onpc-parent-jamie')


def test_mutation_is_outside_read_only_wait_and_result_retries_do_not_repeat_it():
    ui, _, submit, _, in_wait = adapter()
    def mutate(_index):
        assert not in_wait[0], 'normal input must not run inside a retry predicate'
        return True
    submit.action.do_action.side_effect = mutate
    ui.native_app_snapshot.side_effect = [activity_value(),
        accessible_ui.UiError('ui:incomplete-tree'), activity_value()]
    assert ui.natural_expiry(ACTIVITY)['acted'] is True
    submit.action.do_action.assert_called_once_with(0)
    assert ui.native_app_snapshot.call_count == 3


def test_uncertain_mutation_refuses_repeat_without_any_further_discovery():
    ui, _, submit, _, _ = adapter()
    submit.action.do_action.side_effect = TimeoutError('synthetic delivery failure')
    with pytest.raises(TimeoutError):
        ui.natural_expiry(ACTIVITY)
    assert ui.input_uncertain
    calls = ui.native_app_snapshot.call_count, ui.snapshot_owned_target.call_count
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.natural_expiry(ACTIVITY)
    assert calls == (ui.native_app_snapshot.call_count, ui.snapshot_owned_target.call_count)
    submit.action.do_action.assert_called_once_with(0)


@pytest.mark.parametrize('operation', [OBSERVE, ACTIVITY, READY, RESULT])
def test_locked_observation_never_inspects_hidden_native_app(operation):
    ui, _, submit, _, _ = adapter()
    ui.natural_expiry_session.return_value = (SESSION, True)
    ui.native_app_snapshot.side_effect = AssertionError('hidden native app inspection')
    ui.snapshot_owned_target.side_effect = AssertionError('hidden desktop inspection')
    value = ui.natural_expiry(operation)
    assert value == observation(locked=True)
    ui.native_app_snapshot.assert_not_called()
    ui.snapshot_owned_target.assert_not_called()
    submit.action.do_action.assert_not_called()


def decoder():
    pending = []
    def call(_argv, **_kwargs):
        return json.dumps(pending.pop(0)).encode()
    transport = SimpleNamespace(call=Mock(side_effect=call))
    ui = UiObservations(transport)
    ui.boot_guard = BOOT
    def read(operation, value, *, boot=BOOT):
        pending.append({'operation': operation, 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider', 'boot_sha256': boot,
            'natural_expiry': copy.deepcopy(value)})
        return ui.observe(operation)['natural_expiry']
    return ui, transport, read


@pytest.mark.parametrize('fault', ['boot', 'session', 'source', 'app-state'])
def test_decoder_pins_boot_session_source_and_finite_activity(fault):
    ui, transport, read = decoder()
    assert read(OBSERVE, observation())['source'] == SOURCE
    changed = observation(acted=True)
    if fault == 'session': changed['session_sha256'] = 'f' * 64
    if fault == 'source': changed['source'] = 'f' * 64
    if fault == 'app-state': changed['activity']['state']['draft'] = 'unexpected draft'
    with pytest.raises((EvidenceError, accessible_ui.UiError)):
        read(ACTIVITY, changed, boot='f' * 64 if fault == 'boot' else BOOT)
    assert transport.call.call_args.args[0][-2:] == [BOOT, SOURCE]


def test_lock_result_requires_prior_ready_proof_before_transport():
    ui, transport, _ = decoder()
    with pytest.raises(EvidenceError, match='order'):
        ui.observe(RESULT)
    transport.call.assert_not_called()


def test_activity_requires_observed_source_before_transport():
    ui, transport, _ = decoder()
    with pytest.raises(EvidenceError, match='natural-expiry-source'):
        ui.observe(ACTIVITY)
    transport.call.assert_not_called()


def test_observed_lock_does_not_substitute_for_lock_input_ready_proof():
    ui, transport, read = decoder()
    read(OBSERVE, observation(locked=True))
    calls = transport.call.call_count
    with pytest.raises(EvidenceError, match='order'):
        ui.observe(RESULT)
    assert transport.call.call_count == calls


@pytest.mark.parametrize('fault', [None, 'surface', 'session', 'desktop', 'owner'])
def test_lock_result_pins_ready_lock_surface_session_and_input_owner(fault):
    _, _, read = decoder()
    assert read(OBSERVE, observation(locked=True))['state'] == 'locked'
    assert read(READY, observation(locked=True))['lock']['surface_id'] == SURFACE
    value = observation(locked=fault != 'desktop')
    if fault == 'surface': value['lock']['surface_id'] = 'f' * 64
    if fault == 'session': value['session_sha256'] = 'f' * 64
    if fault == 'owner': value['lock']['owner'] = 'other-fixture-child'
    if fault:
        with pytest.raises((EvidenceError, accessible_ui.UiError)):
            read(RESULT, value)
    else:
        assert read(RESULT, value)['lock'] == lock_value()
