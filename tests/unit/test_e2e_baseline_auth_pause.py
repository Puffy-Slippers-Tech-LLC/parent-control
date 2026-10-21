"""C04w uses private records, fake clocks and bounded waited Perl children.

No VM, display, bus, shared cache, fixture build or new cleanup owner.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import accessible_ui
import baseline_auth_pause as pause
import check_graphical_smoke as smoke
import real_interval
from installed_journey import record_installed_journey
from owned_commands import CommandError
from parent_setup_qualification import BaselineAuthPauseQualification, KioskEntryQualification
from private_artifacts import EvidenceError
from tests.support.e2e_kiosk import WORKER
from tests.support.perl import run_perl
from tests.support.paths import ROOT
from ui_observations import UiObservations


@pytest.mark.parametrize('refusal', [None, *pause.PLAN.screen_tags])
def test_real_worker_order_and_every_refusal_blocks_later_input(monkeypatch, refusal):
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow').replace(
        'onpc_request_flow::run', 'onpc_request_flow::auth_pause').replace(
        'sub record_info { }', "sub record_info { }\nsub type_string { die 'unexpected-text' }")
    worker = worker.replace("$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")
    worker = worker.replace('        return {observed => $stage};', r'''
        return {observed => $stage, challenge => {id => 'return', role => 'parent',
            surface => 'gdm', check => $1}}
            if $stage =~ /\Areturn-recipient-(qualified|rechecked)\z/;
        return {observed => $stage};''')
    worker = worker.replace('    });', "    }, decode_json('" + json.dumps(pause.PLAN.invocations)
        + "'), decode_json('" + json.dumps(pause.PLAN.challenges) + "'));" )
    result = json.loads(run_perl(worker).stdout)
    stages = list(pause.PLAN.screen_tags)
    assert bool(result['ok']) == (refusal is None), result['error']
    assert [item[1] for item in result['events'] if item[0] == 'stage'] == (
        stages if refusal is None else stages[:stages.index(refusal) + 1])
    boundaries = ('recipient-rechecked', 'approval-rechecked', 'return-recipient-rechecked')
    end = len(stages) if refusal is None else stages.index(refusal)
    assert sum(item[0] == 'secret' for item in result['events']) == sum(
        stages.index(stage) < end for stage in boundaries)
    if refusal:
        boundary = result['events'].index(['stage', refusal])
        assert not any(item[0] in ('secret', 'key') for item in result['events'][boundary + 1:])


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


@pytest.mark.parametrize('fault', [None, 'wrong-child', 'zero-grant', 'wrong-grant', 'daily',
                                  'total', 'negative-elapsed', 'stale', 'estimate'])
def test_zero_daily_real_grant_comparison_uses_original_estimate(tmp_path, fault):
    journey = pause.BaselineAuthPauseJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.balance = {'daily': {'seconds': 0, 'precision_seconds': 1},
                       'one_time': {'seconds': 0, 'precision_seconds': 1},
                       'observed_monotonic_ns': 1_000_000_000}
    choice = {'request': dict(pause.CHOICES), 'estimate': {'kind': 'fixed', 'seconds': 75},
              'observed_monotonic_ns': 2_000_000_000}
    journey.check_settings('new-estimate', {'ui': {'valid_choice': choice}})
    choice['estimate']['seconds'] = 999
    value = {'child': 'fixture-child', **{key: accessible_ui.duration_projection(text)
        for key, text in (('daily', '0m'), ('one_time', '1m 10s'), ('total', '1m 10s'))},
        'observed_monotonic_ns': 52_000_000_000}
    if fault == 'wrong-child': value['child'] = 'existing-fixture-child'
    if fault in ('zero-grant', 'wrong-grant', 'daily', 'total'):
        key, text = {'zero-grant': ('one_time', '0m'), 'wrong-grant': ('one_time', '1m 30s'),
                     'daily': ('daily', '0m 1s'), 'total': ('total', '0m 20s')}[fault]
        value[key] = accessible_ui.duration_projection(text)
    if fault == 'negative-elapsed': value['observed_monotonic_ns'] = 1_000_000_000
    if fault == 'stale': value['observed_monotonic_ns'] = 603_000_000_000
    if fault == 'estimate': journey.grant_estimate['estimate']['seconds'] = 975
    observed = {'ui': {'time_explanation': value}}
    if fault:
        with pytest.raises(EvidenceError): journey.check_settings('approved-balance', observed)
        assert not journey.grant_observed
    else:
        journey.check_settings('approved-balance', observed)
        assert journey.grant_observed and observed['comparison']['independent_grant']
        with pytest.raises(EvidenceError, match='balance-replay'):
            journey.check_settings('approved-balance', observed)


def test_real_recorder_constructs_pause_journey_with_bounded_action(tmp_path):
    recorder = MagicMock()
    recorder.assertion = Mock()
    recorder.artifact.return_value = 'artifact'
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
        verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is pause.BaselineAuthPauseJourney and journey.plan is pause.PLAN
        assert set(journey.actions) == {'real-interval'}
        assert options['timeout'] == 1800 and options['authenticate'] is True
        raise EvidenceError('synthetic-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-stop'):
        record_installed_journey(recorder, context, pause.PLAN,
                                 journey_type=pause.BaselineAuthPauseJourney)
    recorder.assertion.assert_not_called()


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


def test_registration_and_snapshot_reuse(tmp_path, monkeypatch):
    import check_e2e_baseline_auth_pause as selector
    import test_commands
    assert issubclass(BaselineAuthPauseQualification, KioskEntryQualification)
    assert BaselineAuthPauseQualification.journey(SimpleNamespace(directory=tmp_path), Mock()).plan is pause.PLAN
    assets = object()
    named, execute = Mock(return_value=assets), Mock(return_value=0)
    monkeypatch.setattr(selector, 'named_input', named)
    monkeypatch.setattr(selector, 'smoke', execute)
    assert selector.main() == 0
    named.assert_called_once_with(package_source=True)
    execute.assert_called_once_with(assets=assets, provision_credentials=True, baseline_auth_pause=True)
    assert test_commands.qualification_input_options(
        ROOT,
        'check_e2e_baseline_auth_pause') == {'package_source': True}


@pytest.mark.parametrize('kwargs', [dict(baseline_auth_pause=True),
    dict(baseline_auth_pause=True, assets='synthetic', provision_credentials=True, kiosk_entry=True)])
def test_conflicting_registration_refuses_before_resource_discovery(kwargs):
    with pytest.raises(CommandError, match='baseline-auth-pause-prerequisites'):
        smoke.main(**kwargs)
