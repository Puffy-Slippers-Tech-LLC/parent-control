"""Shared installed controller with real durable recorder; no VM operations."""

from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import evidence
import installed_journey as journeys
import parent_about
from private_artifacts import EvidenceError, PrivateCollector
from recording import ScenarioRecorder
from tests.support.paths import ROOT


SYNTHETIC = journeys.JourneyPlan(
    prefix='example', worker_mode='example_view',
    screen_tags={'installed-greeter': 'onpc-example-greeter', 'opened': 'onpc-example-opened',
                 'details': 'onpc-example-details', 'returned': 'onpc-example-opened'},
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            'opened': 'step-1', 'details': 'step-1', 'returned': 'step-2'},
    advance_after={'details': 'step-2'},
)


@pytest.mark.parametrize('plan', [parent_about.PLAN, SYNTHETIC], ids=['parent', 'different-consumer'])
@pytest.mark.parametrize('failure', [None, 'observation-write', 'return-step-write', 'worker-loss'])
def test_shared_plan_records_before_input_and_latches_transition_failures(
        tmp_path, monkeypatch, plan, failure):
    # A different trusted plan exercises the same recorder phase shape without
    # registering a synthetic scenario or awarding it any customer coverage.
    inventory = ROOT / 'tests/e2e/scenarios.json'
    inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in evidence.INPUT_FIELDS}
    inputs.update(inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(),
                  environment_id='ubuntu26-04-pinned')
    contract = evidence.EvidenceContract(inventory_path=inventory, root=ROOT,
        selector='E2E-030/parent', run_id='shared-controller-test', inputs=inputs)
    directory = tmp_path / 'raw'
    directory.mkdir()
    (directory / 'testresults').mkdir()
    details = []
    for index, (stage, tag) in enumerate(plan.screen_tags.items()):
        details.extend([
            {'needle': tag, 'result': 'ok', 'area': [{'result': 'ok', 'similarity': 100}],
             'screenshot': f'smoke-{index}.png'},
            {'title': plan.prefix + '-' + stage, 'result': 'ok'},
        ])
    (directory / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
    monkeypatch.setattr(journeys, 'screenshot', lambda *_: {'sha256': 'a' * 64})
    monkeypatch.setattr(journeys.system, 'address', Mock(return_value='fixture-host'))
    monkeypatch.setattr(journeys, 'Transport', Mock())
    setup = Mock(return_value={'package_verified': True, 'setup_reboot_verified': True})
    monkeypatch.setattr(journeys, 'InstalledSetup', Mock(return_value=SimpleNamespace(run=setup)))
    boot = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    monkeypatch.setattr(journeys, 'ReadOnlyObservations', Mock(return_value=boot))
    boundary = next(iter(plan.advance_after))
    state = {'stage': None, 'stored': False}
    context = SimpleNamespace(directory=directory, host_key='fixture-key', commands=Mock(),
        guestfs=Mock(), credentials=Mock(), verified=SimpleNamespace(inputs=inputs),
        lease=SimpleNamespace(source=SimpleNamespace(uuid='fixture-uuid'),
            view=SimpleNamespace(domain_id=7), state={'run': 'a' * 32}, guard=Mock()))

    with PrivateCollector(run_id=contract.run_id, secrets=[], parent=tmp_path) as collector:
        recorder = ScenarioRecorder(contract, collector)
        recorder.begin_case('E2E-030/parent')
        save = collector.save_report

        def checkpoint(name, value):
            if state['stage'] == boundary:
                if (failure == 'observation-write' and value.get('event') == 'observation') or (
                        failure == 'return-step-write' and value.get('event') == 'step-started'
                        and value['active_step'] == 'step-2'):
                    raise OSError('fixed checkpoint failure')
            result = save(name, value)
            if value.get('event') == 'observation':
                assert not (directory / (state['stage'] + '.reply.json')).exists()
                state['stored'] = True
            return result

        monkeypatch.setattr(collector, 'save_report', checkpoint)
        acknowledged = []

        def worker(**options):
            assert options['authenticate'] is True
            assert options['guarded_observe'].__self__.review is False
            for stage in plan.stages:
                state.update(stage=stage, stored=False)
                request = directory / (stage + '.request.json')
                request.write_text(json.dumps({'stage': stage, 'screenshot': None}))

                def guard():
                    assert not (directory / (stage + '.reply.json')).exists()
                    if failure == 'worker-loss' and stage == boundary and state['stored']:
                        raise RuntimeError('fixed worker loss')

                try:
                    options['guarded_observe'](guard)
                except (OSError, RuntimeError):
                    assert not (directory / (stage + '.reply.json')).exists()
                    with pytest.raises(EvidenceError, match='previous-failure'):
                        options['guarded_observe'](Mock())
                    raise
                assert state['stored']
                assert recorder._active['step_id'] == plan.advance_after.get(stage, plan.phases[stage])
                reply = json.loads((directory / (stage + '.reply.json')).read_bytes())
                if stage == 'ready':
                    assert reply == {plan.worker_mode: True}
                acknowledged.append(stage)
            assert [s['stage'] for s in options['validate']()] == list(plan.screen_tags)
            return dict(outcome='passed', shutdown_verified=True, worker_stopped=True, callback_closed=True)

        context.run_worker = worker
        if failure:
            with pytest.raises((OSError, RuntimeError)):
                journeys.record_installed_journey(recorder, context, plan)
            assert acknowledged == list(plan.stages[:plan.stages.index(boundary)])
            assert recorder.records[0]['failures']
        else:
            journeys.record_installed_journey(recorder, context, plan)
            assert acknowledged == list(plan.stages)
            steps = recorder.records[0]['steps']
            assert [s['step_id'] for s in steps] == ['setup', 'start', 'step-1', 'step-2', 'end']
            assert all(s['outcome'] == 'passed' for s in steps)
            assert steps[-2]['assertion_ids'] == ['visible-result']
        assert recorder._active is None
        setup.assert_called_once()
        assert boot.read.call_args_list and all(call.args == ('boot',) for call in boot.read.call_args_list)


def test_invalid_phase_plan_refuses_before_credentials_or_worker(tmp_path):
    context = SimpleNamespace(credentials=Mock(), run_worker=Mock())
    with pytest.raises(EvidenceError, match='phase-plan'):
        journeys.record_installed_journey(Mock(), context, replace(SYNTHETIC, phases={}))
    context.credentials.provision.assert_not_called()
    context.run_worker.assert_not_called()


def test_review_requires_a_named_qualification_mode(tmp_path):
    with pytest.raises(EvidenceError, match='review-mode'):
        journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), SYNTHETIC, review=True)


def test_stage_action_runs_after_worker_guard_and_before_durable_reply(tmp_path, monkeypatch):
    plan = replace(SYNTHETIC, screen_tags={"created": "onpc-example-created"},
                   phases={"ready": "setup", "setup-detached": "setup", "created": "step-1"},
                   stage_actions={"created": "create-account"})
    directory = tmp_path
    for stage in plan.stages:
        (directory / (stage + ".request.json")).write_text(
            json.dumps({"stage": stage, "screenshot": None}))
    monkeypatch.setattr(journeys.system, "address", Mock(return_value="fixture-host"))
    transport = Mock()
    monkeypatch.setattr(journeys, "Transport", Mock(return_value=transport))
    monkeypatch.setattr(journeys, "InstalledSetup", Mock(return_value=SimpleNamespace(
        run=Mock(return_value={"package_verified": True}))))
    monkeypatch.setattr(journeys, "ReadOnlyObservations", Mock(return_value=SimpleNamespace(
        read=Mock(return_value={"boot_sha256": "b" * 64}))))
    context = SimpleNamespace(directory=directory, host_key="fixture-key", commands=Mock(),
        verified=Mock(), lease=SimpleNamespace(source=SimpleNamespace(uuid="fixture-uuid"),
        view=SimpleNamespace(domain_id=7), state={"run": "a" * 32}, guard=Mock()))
    events = []

    def action(journey, guard):
        assert journey.transport is transport
        assert not (directory / "created.reply.json").exists()
        guard()
        events.append("action")
        return {"eligible_account_created": True}

    journey = journeys.InstalledJourney(
        context, lambda stage, observed: events.append((stage, observed)), plan,
        actions={"create-account": action},
    )
    for _stage in plan.stages:
        journey.step(lambda: events.append("guard"))

    created = next(event[1] for event in events
                   if isinstance(event, tuple) and event[0] == "created")
    assert created["fixture"] == {"eligible_account_created": True}
    assert events.index("action") < events.index(("created", created))
    assert json.loads((directory / "created.reply.json").read_text()) == {"observed": "created"}


def test_stage_action_registry_refuses_missing_or_extra_actions(tmp_path):
    plan = replace(SYNTHETIC, stage_actions={"details": "create-account"})
    with pytest.raises(EvidenceError, match="stage-actions"):
        journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
