"""Desktop-session qualification preserves durable acknowledgement and ownership."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import desktop_session
from private_artifacts import EvidenceError


@pytest.mark.parametrize('plan', [desktop_session.LOGOUT_PLAN, desktop_session.SWITCH_PLAN],
                         ids=['logout', 'switch'])
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


@pytest.mark.parametrize('plan', [desktop_session.LOGOUT_PLAN, desktop_session.SWITCH_PLAN],
                         ids=['logout', 'switch'])
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
        'operation': 'desktop', 'outcome': 'passed', 'interface': 'AT-SPI',
        'boot_sha256': 'b' * 64,
    }).encode()))
    with pytest.raises(EvidenceError, match='boot-changed'):
        journey.step(Mock())
    journey.transport.call.assert_called_once()
    assert journey.transport.call.call_args.args[0][-1] == 'a' * 64
    journey.vm.read.assert_not_called()
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()
