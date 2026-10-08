"""Desktop-session qualification preserves durable acknowledgement and ownership."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import desktop_session
from private_artifacts import EvidenceError


@pytest.mark.parametrize('plan', [desktop_session.LOGOUT_PLAN, desktop_session.SWITCH_PLAN,
                                 desktop_session.LOCK_PLAN, desktop_session.SUPPLIED_LOCK_PLAN],
                         ids=['logout', 'switch', 'lock', 'supplied-lock'])
@pytest.mark.parametrize('failure', [None, 'checkpoint', 'worker-loss'])
def test_next_input_requires_persisted_observation_and_current_worker(tmp_path, plan, failure):
    reply = tmp_path / 'ready.reply.json'
    (tmp_path / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    recorded = []

    def progress(stage, observed):
        assert not reply.exists()
        if failure == 'checkpoint':
            raise OSError('checkpoint failed')
        recorded.append(stage)

    def guard():
        assert not reply.exists()
        if recorded and failure == 'worker-loss':
            raise RuntimeError('worker stopped')

    journey = desktop_session.DesktopSessionJourney(
        SimpleNamespace(directory=tmp_path), progress, plan)
    if failure:
        with pytest.raises((OSError, RuntimeError)):
            journey.step(guard)
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
    else:
        journey.step(guard)
        assert recorded == ['ready']
        assert json.loads(reply.read_text()) == {plan.worker_mode: True}


@pytest.mark.parametrize('plan', [desktop_session.LOGOUT_PLAN, desktop_session.SWITCH_PLAN,
                                 desktop_session.LOCK_PLAN, desktop_session.SUPPLIED_LOCK_PLAN],
                         ids=['logout', 'switch', 'lock', 'supplied-lock'])
def test_boot_replacement_refuses_before_next_customer_action(tmp_path, plan):
    stage = 'desktop'
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    progress = Mock()
    journey = desktop_session.DesktopSessionJourney(
        SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    journey.transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        'operation': 'desktop', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
        'boot_sha256': 'b' * 64,
    }).encode()))
    with pytest.raises(EvidenceError, match='boot-changed'):
        journey.step(Mock())
    journey.transport.call.assert_called_once()
    assert journey.transport.call.call_args.args[0][-1] == 'a' * 64
    journey.vm.read.assert_not_called()
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('failure', ['', 'checkpoint', 'worker-loss', 'changed-surface'])
def test_actual_lock_reveal_recorder_decoder_refuses_before_reply(tmp_path, failure):
    from ui_observations import UiObservations
    plan = desktop_session.LOCK_PLAN
    stage = 'reveal-ready'
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    reply = tmp_path / (stage + '.reply.json')
    observed = []

    def progress(current, result):
        assert not reply.exists()
        assert result['ui']['lock']['desktop_input_available'] is False
        if failure == 'checkpoint': raise OSError('checkpoint failed')
        observed.append(current)

    guard = Mock(side_effect=lambda: (_ for _ in ()).throw(RuntimeError('worker lost'))
                 if observed and failure == 'worker-loss' else None)
    journey = desktop_session.DesktopSessionJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': s} for s in plan.stages[:plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.transport = SimpleNamespace(call=Mock(return_value=json.dumps({
        'operation': 'parent-lock-reveal-ready', 'outcome': 'passed',
        'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'a' * 64,
        'lock': {'entry': 'curtain', 'owner': 'fixture-parent', 'locked': True,
            'desktop_input_available': False, 'recipient': None,
            'surface_id': ('c' if failure == 'changed-surface' else 'b') * 64,
            'provider': {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}}}).encode()))
    journey.ui = UiObservations(journey.transport)
    journey.ui.lock_surface_id = 'b' * 64
    if failure:
        with pytest.raises((OSError, RuntimeError, EvidenceError)): journey.step(guard)
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(guard)
        assert observed == [stage]
        assert json.loads(reply.read_text()) == {'observed': stage}
