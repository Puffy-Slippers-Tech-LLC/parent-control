"""C04w credential continuity uses private records and fake clocks.

No VM, display, bus, shared cache, fixture build or new cleanup owner.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
import baseline_auth_pause as pause
import check_graphical_smoke as smoke
import real_interval
from owned_commands import CommandError
from private_artifacts import EvidenceError
from ui_observations import UiObservations


def mate_value(operation, *, identity='a' * 64, provider=None):
    return {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
            'boot_sha256': 'b' * 64,
            'approval': {'challenge_id': identity, 'provider': provider or {
                'version': '1.26.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}}}


@pytest.mark.parametrize('fault', [None, 'too-early', 'too-late', 'replacement', 'provider',
                                  'skip-first', 'stale-second', 'stale-submit', 'intervening'])
def test_pause_retains_identity_but_requires_two_fresh_recipient_proofs(monkeypatch, fault):
    now = [100.0]
    monkeypatch.setattr(real_interval.time, 'monotonic', lambda: now[0])
    observer = UiObservations(Mock())
    observer.boot_guard = 'b' * 64
    observer.call = Mock(side_effect=lambda command, operation, **kw: (
        json.dumps(mate_value(operation, identity='b' * 64 if fault == 'replacement'
            and operation.endswith('qualified') else 'a' * 64,
            provider={'version': '1.26.2', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
                if fault == 'provider' and operation.endswith('qualified') else None)).encode(), []))
    observer.observe(accessible_ui.PAUSE_MATE_ORDER[0])
    now[0] += 44 if fault == 'too-early' else 135 if fault == 'too-late' else 45
    if fault in ('too-early', 'too-late', 'replacement', 'provider', 'skip-first', 'intervening'):
        operation = (accessible_ui.PAUSE_MATE_ORDER[2] if fault == 'skip-first' else
                     'kiosk-valid-fraction-soft-read' if fault == 'intervening' else
                     accessible_ui.PAUSE_MATE_ORDER[1])
        expected = {'too-early': 'mate-pause-bound', 'too-late': 'mate-pause-bound',
                    'replacement': 'mate-replacement', 'provider': 'mate-provider-changed',
                    'skip-first': 'mate-order', 'intervening': 'mate-intervening-operation'}[fault]
        with pytest.raises(EvidenceError, match=expected):
            observer.observe(operation)
        assert observer.challenge_failed
        with pytest.raises(EvidenceError):
            observer.observe(accessible_ui.PAUSE_MATE_ORDER[1])
        return
    observer.observe(accessible_ui.PAUSE_MATE_ORDER[1])
    now[0] += 30 if fault == 'stale-second' else 1
    if fault == 'stale-second':
        with pytest.raises(EvidenceError, match='mate-stale-proof'):
            observer.observe(accessible_ui.PAUSE_MATE_ORDER[2])
    else:
        observer.observe(accessible_ui.PAUSE_MATE_ORDER[2])
        assert observer.mate_approval_index == 3
        assert observer.mate_approval_identity == 'a' * 64
        if fault == 'stale-submit':
            now[0] += 30
            before = observer.call.call_count
            with pytest.raises(EvidenceError, match='mate-stale-proof'):
                observer.observe(accessible_ui.PAUSE_MATE_ORDER[3])
            assert observer.call.call_count == before


@pytest.mark.parametrize('failure', [False, True])
def test_open_observation_waits_under_attempt_guard_before_durable_reply(tmp_path, monkeypatch, failure):
    now = [1000.0]
    monkeypatch.setattr(real_interval.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(real_interval.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    journey = pause.BaselineAuthPauseJourney(SimpleNamespace(directory=tmp_path), Mock())
    stage = 'approval-open'
    journey.steps = [{'stage': value} for value in pause.PLAN.stages[:pause.PLAN.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.collect_failure = Mock()
    public = Mock(return_value=mate_value(accessible_ui.PAUSE_MATE_ORDER[0]))
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=public)
    reply = tmp_path / (stage + '.reply.json')
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    def guard():
        assert not reply.exists()
        if failure and now[0] >= 1015:
            raise EvidenceError('synthetic-owner-lost')
        return 2000.0
    journey.progress.side_effect = lambda *args: (public.assert_called_once(),
        pytest.fail('early reply') if reply.exists() else None)
    if failure:
        with pytest.raises(EvidenceError, match='synthetic-owner-lost'):
            journey.step(guard)
        assert not reply.exists() and journey.failed
        journey.progress.assert_not_called()
        assert now[0] < 1045
    else:
        journey.step(guard)
        assert reply.exists() and now[0] == 1045
        assert journey.steps[-1]['fixture'] == 45
    public.assert_called_once_with(accessible_ui.PAUSE_MATE_ORDER[0])


@pytest.mark.parametrize('kwargs', [dict(baseline_auth_pause=True),
    dict(baseline_auth_pause=True, assets='synthetic', provision_credentials=True, kiosk_entry=True)])
def test_conflicting_registration_refuses_before_resource_discovery(kwargs):
    with pytest.raises(CommandError, match='baseline-auth-pause-prerequisites'):
        smoke.main(**kwargs)
