"""TIME03 fake-clock safety and actual bounded worker composition; no VM."""
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui
from accessible_ui import AccessibleUI, UiError
from private_artifacts import EvidenceError
import real_interval as interval
from real_interval_qualification import PLAN, RealIntervalJourney
from tests.support.perl import ALLOWANCE_WORKER, run_perl
from tests.support.accessible_ui import Node, ui_for
from ui_observations import UiObservations


@pytest.fixture
def clock(monkeypatch):
    value = SimpleNamespace(now=100.0, sleeps=[])
    monkeypatch.setattr(interval.time, 'monotonic', lambda: value.now)
    def sleep(seconds):
        value.sleeps.append(seconds)
        value.now += seconds
    monkeypatch.setattr(interval.time, 'sleep', sleep)
    return value


@pytest.mark.parametrize('early', [False, True])
def test_complete_real_duration_and_finite_checkpoints(clock, monkeypatch, early):
    if early:
        original = interval.time.sleep
        monkeypatch.setattr(interval.time, 'sleep', lambda seconds: original(min(seconds, .125)))
    guard, progress = Mock(), Mock()
    elapsed = interval.wait_real_interval(5, deadline=110, guard=guard, progress=progress)
    assert elapsed == 5 and type(elapsed) is float
    assert [call.args for call in progress.call_args_list] == [(i, i * 1.25) for i in range(5)]
    assert max(clock.sleeps) <= .25 and guard.call_count > len(clock.sleeps)


@pytest.mark.parametrize('duration', [True, 0, -1, 301, float('inf'), float('nan'), '5'])
def test_invalid_duration_never_calls_guard_or_sleeps(clock, duration):
    guard = Mock()
    with pytest.raises(EvidenceError, match='time03:duration'):
        interval.wait_real_interval(duration, deadline=110, guard=guard, progress=Mock())
    guard.assert_not_called()
    assert not clock.sleeps


@pytest.mark.parametrize('deadline', [True, float('inf'), float('nan'), None, 105])
def test_invalid_or_insufficient_deadline(clock, deadline):
    with pytest.raises(EvidenceError, match='time03:(deadline|insufficient-budget)'):
        interval.wait_real_interval(5, deadline=deadline, guard=Mock(), progress=Mock())
    assert not clock.sleeps


@pytest.mark.parametrize('boundary', ['sleep', 'guard', 'progress'])
def test_deadline_crossing_cannot_return_elapsed(clock, monkeypatch, boundary):
    def advance(*_):
        clock.now = 110
    guard, progress = Mock(), Mock()
    if boundary == 'sleep': monkeypatch.setattr(interval.time, 'sleep', advance)
    elif boundary == 'progress': progress.side_effect = advance
    else:
        calls = []
        def check():
            calls.append(1)
            if len(calls) > 1: advance()
        guard.side_effect = check
    with pytest.raises(EvidenceError, match='time03:(deadline|insufficient-budget)'):
        interval.wait_real_interval(5, deadline=110, guard=guard, progress=progress)


@pytest.mark.parametrize('failure', [RuntimeError('lost-owner'), KeyboardInterrupt(), OSError('progress')])
def test_guard_and_progress_failures_propagate(clock, failure):
    guard, progress = Mock(), Mock()
    if isinstance(failure, OSError): progress.side_effect = failure
    else: guard.side_effect = [None, None, failure]
    with pytest.raises(type(failure)) as caught:
        interval.wait_real_interval(5, deadline=110, guard=guard, progress=progress)
    assert caught.value is failure and clock.now < 105


def about_value():
    return {'pid': 123, 'endpoint': [':1.2', '/about'],
            'product': accessible_ui.PRODUCT, 'version': '1.1'}


@pytest.mark.parametrize('fault', [None, 'missing', 'wrong-version', 'endpoint', 'pid', 'extra'])
def test_real_controller_decodes_bounded_about_observation(monkeypatch, tmp_path, fault):
    from tests.support.paths import ROOT
    value = about_value()
    value['version'] = json.loads((ROOT / 'data/app.json').read_text())['version']
    if fault == 'wrong-version': value['version'] += '.999'
    if fault == 'endpoint': value['endpoint'] = ['bad', '/about']
    if fault == 'pid': value['pid'] = True
    if fault == 'extra': value['private'] = 'canary'
    result = {'operation': 'about-interval-read', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
              **({} if fault == 'missing' else {'about_interval': value})}
    transport = Mock()
    transport.call.return_value = json.dumps(result).encode()
    if fault:
        with pytest.raises(EvidenceError, match='ui:about-interval-response'):
            UiObservations(transport).observe('about-interval-read')
    else:
        assert UiObservations(transport).observe('about-interval-read') == result


def test_public_read_never_opens_about_and_refuses_missing_entry():
    ui = object.__new__(AccessibleUI)
    root = SimpleNamespace(bus=':1.2', path='/about', get_process_id=lambda: 123)
    ui.snapshot_owned_target = Mock(return_value=root)
    ui.read_label = Mock(return_value=True)
    ui.activate_id = Mock(side_effect=AssertionError('must not input'))
    assert ui.read_about_interval('1.1') == about_value()
    ui.snapshot_owned_target.return_value = None
    with pytest.raises(UiError, match='ui:about-interval-entry'):
        ui.read_about_interval('1.1')
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'delayed-parent', 'incomplete-absence',
                                  'missing-parent', 'open-about', 'wrong-owner',
                                  'duplicate', 'prompt'])
def test_wrong_entry_waits_for_complete_readiness_without_input(monkeypatch, clock, fault):
    parent = Node(identity='parent-window')
    application = Node(identity=accessible_ui.PARENT_APPLICATION, children=[parent])
    if fault == 'missing-parent':
        application.children = []
    elif fault == 'open-about':
        parent.children = [Node(identity='about-dialog')]
    elif fault == 'duplicate':
        application.children.append(Node(identity='parent-window'))
    ui = ui_for(application)
    if fault == 'wrong-owner':
        application.identity = 'foreign-application'
    ui.timeout = 1
    ui.activate_id = Mock(side_effect=AssertionError('must not input'))
    ui.read_about_interval = Mock(wraps=ui.read_about_interval)
    if fault == 'delayed-parent':
        application.children = []
        original_sleep = interval.time.sleep
        def show_parent(seconds):
            original_sleep(seconds)
            application.children = [parent]
        monkeypatch.setattr(interval.time, 'sleep', show_parent)
    elif fault == 'incomplete-absence':
        original_absent = ui.absent_id
        attempts = []
        def absent(*args, **kwargs):
            attempts.append(1)
            return False if len(attempts) == 1 else original_absent(*args, **kwargs)
        ui.absent_id = absent
    elif fault == 'prompt':
        ui.handle_system_prompt = Mock(side_effect=UiError('ui:unexpected-system-prompt'))
    if fault in ('missing-parent', 'open-about', 'wrong-owner', 'duplicate', 'prompt'):
        with pytest.raises(UiError):
            ui.run('about-interval-refused', '1.1')
        ui.read_about_interval.assert_not_called()
    else:
        assert ui.run('about-interval-refused', '1.1')['outcome'] == 'passed'
        ui.read_about_interval.assert_called_once_with('1.1')
        assert bool(clock.sleeps) == (fault is not None)
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'ownership', 'deadline', 'progress', 'changed-window', 'interrupt'])
def test_real_stage_action_refuses_reply_and_latches_failure(tmp_path, clock, fault):
    plan = replace(PLAN, screen_tags={'first': 'ui:about-interval-read', 'second': 'ui:about-interval-read'},
                   stage_actions={'first': 'real-interval'}, phases={})
    progress = Mock(side_effect=OSError('storage') if fault == 'progress' else None)
    journey = RealIntervalJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
    journey.boot = 'a' * 64
    value = about_value()
    def observe(operation):
        return {'operation': operation, 'about_interval': value.copy(), 'outcome': 'passed'}
    journey.ui = SimpleNamespace(boot_proof='a' * 64, observe=observe)
    def guard():
        if clock.now >= 101 and fault in ('ownership', 'interrupt'):
            raise KeyboardInterrupt() if fault == 'interrupt' else RuntimeError('lost-owner')
        if fault == 'deadline' and clock.now >= 101: clock.now = 110
        return 110
    (tmp_path / 'first.request.json').write_text(json.dumps({'stage': 'first', 'screenshot': None}))
    if fault in ('ownership', 'deadline', 'progress', 'interrupt'):
        with pytest.raises((RuntimeError, OSError, KeyboardInterrupt, EvidenceError)):
            journey.step(guard)
        assert not (tmp_path / 'first.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(guard)
    else:
        journey.step(guard)
        assert journey.steps[-1]['fixture'] == 5 and clock.now == 105
        value['endpoint'] = [':1.2', '/other'] if fault else [':1.2', '/about']
        (tmp_path / 'second.request.json').write_text(json.dumps({'stage': 'second', 'screenshot': None}))
        if fault:
            with pytest.raises(EvidenceError, match='about-window-changed'):
                journey.step(guard)
            assert not (tmp_path / 'second.reply.json').exists()
        else:
            journey.step(guard)
            assert clock.now == 105 and (tmp_path / 'second.reply.json').exists()


def test_actual_worker_order_and_every_refusal(monkeypatch):
    script = ALLOWANCE_WORKER.replace('onpc_set_allowance', 'onpc_parent_about')
    script = script.replace('onpc_parent_about::run(', 'onpc_parent_about::run_interval(')
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script).stdout)
    assert success['ok'], success['error']
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == list(PLAN.screen_tags)
    for stage in PLAN.screen_tags:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        assert result['events'] == success['events'][:success['events'].index(['stage', stage]) + 1]


def test_selector_reuses_owned_installed_envelope(monkeypatch, tmp_path):
    import check_e2e_wait_a_bounded_real_interval_under_the_attempt_guard as selector
    import check_graphical_smoke as smoke
    import parent_setup_qualification as qualification
    from owned_commands import CommandError
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0 and run.call_args.kwargs['real_interval'] is True
    with pytest.raises(CommandError, match='real-interval-prerequisites'):
        smoke.main(real_interval=True)
    for option in ('app_restart', 'parent_about', 'feedback_reset'):
        with pytest.raises(CommandError, match='real-interval-prerequisites'):
            smoke.main(real_interval=True, assets=tmp_path, provision_credentials=True, **{option: True})
    context = SimpleNamespace(directory=tmp_path)
    assert qualification.RealIntervalQualification.journey(context, Mock()).plan is PLAN
    assert qualification.RealIntervalQualification.finalize is qualification.KioskEntryQualification.finalize
    assert qualification.RealIntervalQualification.prepare_context is qualification.KioskEntryQualification.prepare_context
