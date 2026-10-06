"""TIME01 public identity, complete absence, elapsed bounds and durable refusals.

Only synthetic trees, clocks, transport doubles and private pytest files.
No real desktop, account/session command, socket, VM or shared mutable state.
"""

from dataclasses import FrozenInstanceError
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
import check_e2e_countdown as check
from countdown import CountdownObservation, check_countdown_balance
from countdown_qualification import CountdownJourney, PLAN, OFF_PLAN
from parent_setup_qualification import CountdownQualification, CountdownOffQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import UiObservations


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
