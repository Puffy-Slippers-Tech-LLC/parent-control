"""Shared installed controller with real durable recorder; no VM operations."""

from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import evidence
import installed_journey as journeys
import installed_setup
import parent_about
import parent_access
import parent_terminal
import parent_discovery
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


@pytest.mark.parametrize('fault', [None, 'wrong-reply', 'timeout', 'lost-worker', 'review', 'replay'])
def test_shared_system_prompt_rendezvous_retains_request_and_refuses_uncertain_input(tmp_path, monkeypatch, fault):
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), parent_access.PLAN,
                                        review=fault == 'review')
    request = tmp_path / 'app-grid.prompt-1.request.json'
    reply = tmp_path / 'app-grid.prompt-1.reply.json'
    if fault == 'replay': request.write_text('{}')
    guard = Mock(side_effect=RuntimeError('lost worker') if fault == 'lost-worker' else None)
    ticks = iter([0, 16])
    if fault == 'timeout': monkeypatch.setattr(journeys.time, 'monotonic', lambda: next(ticks))
    def worker(_):
        assert request.exists()
        assert not (tmp_path / 'app-grid.reply.json').exists()
        assert guard.call_count == 2
        assert guard.call_args.kwargs == {'service': True}
        assert json.loads(request.read_text()) == {'stage': 'app-grid', 'sequence': 1,
            'kind': 'login-keyring', 'ui_pointer': {'x': 200, 'y': 330}}
        value = {'stage': 'app-grid', 'sequence': 1, 'action': 'cancel-click', 'outcome': 'sent'}
        if fault == 'wrong-reply': value['sequence'] = 2
        reply.write_text(json.dumps(value))
    monkeypatch.setattr(journeys.time, 'sleep', worker)
    if fault:
        with pytest.raises((EvidenceError, RuntimeError)):
            journey.dismiss_system_prompt('app-grid', {'x': 200, 'y': 330}, guard)
    else:
        journey.dismiss_system_prompt('app-grid', {'x': 200, 'y': 330}, guard)
        assert guard.call_count == 3
    assert not (tmp_path / 'app-grid.reply.json').exists()


@pytest.mark.parametrize('plan', [parent_about.PLAN, SYNTHETIC, parent_discovery.PLAN,
                                 parent_discovery.EMPTY_PLAN, parent_access.PLAN, parent_terminal.PLAN],
                         ids=['parent', 'different-consumer', 'discovery', 'empty', 'standard-access', 'terminal'])
@pytest.mark.parametrize('failure', [None, 'observation-write', 'return-step-write', 'worker-loss'])
def test_shared_plan_records_before_input_and_latches_transition_failures(
        tmp_path, monkeypatch, plan, failure):
    # A different trusted plan exercises the same recorder phase shape without
    # registering a synthetic scenario or awarding it any customer coverage.
    inventory = ROOT / 'tests/e2e/scenarios.json'
    inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in evidence.INPUT_FIELDS}
    inputs.update(inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(),
                  environment_id='ubuntu26-04-pinned')
    selector = ('E2E-003/existing-and-new' if plan is parent_discovery.PLAN else 'E2E-030/parent')
    if plan is parent_discovery.EMPTY_PLAN:
        selector = 'E2E-003/none'
    if plan is parent_access.PLAN:
        selector = 'E2E-004/app-grid'
    if plan is parent_terminal.PLAN:
        selector = 'E2E-004/terminal'
    contract = evidence.EvidenceContract(inventory_path=inventory, root=ROOT,
        selector=selector, run_id='shared-controller-test', inputs=inputs)
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
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock(return_value=SimpleNamespace(run=setup)))
    boot = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    monkeypatch.setattr(journeys, 'ReadOnlyObservations', Mock(return_value=boot))
    def observe_ui(operation):
        import accessible_ui
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'standard-app-grid':
            result['pointer'] = {'x': 700, 'y': 80}
        if operation in accessible_ui.SETTINGS_OPERATIONS:
            result['settings'] = {'child': accessible_ui.CHILD_IDENTITIES[
                accessible_ui.SETTINGS_OPERATIONS[operation]], 'limit_enabled': False,
                'allowance': ['1 hour'] if operation.startswith('new-') else ['0 minutes']}
        return result
    monkeypatch.setattr(journeys, 'UiObservations', Mock(return_value=SimpleNamespace(observe=observe_ui)))
    boundary = next(stage for stage, phase in plan.advance_after.items() if phase == 'step-2')
    state = {'stage': None, 'stored': False}
    context = SimpleNamespace(directory=directory, host_key='fixture-key', commands=Mock(),
        installed_snapshot='onpc-v1.1',
        guestfs=Mock(), credentials=Mock(), verified=SimpleNamespace(inputs=inputs),
        lease=SimpleNamespace(source=SimpleNamespace(uuid='fixture-uuid'),
            view=SimpleNamespace(domain_id=7), state={'run': 'a' * 32}, guard=Mock()))

    with PrivateCollector(run_id=contract.run_id, secrets=[], parent=tmp_path) as collector:
        recorder = ScenarioRecorder(contract, collector)
        recorder.begin_case(selector)
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
                if plan is parent_access.PLAN and stage == 'app-grid':
                    assert reply == {'observed': stage, 'ui_pointer': {'x': 700, 'y': 80}}
                if plan is parent_access.PLAN and stage == 'system-prompt':
                    assert reply == {'observed': stage}
                acknowledged.append(stage)
            assert [s['stage'] for s in options['validate']()] == list(plan.screen_tags)
            return dict(outcome='passed', shutdown_verified=True, worker_stopped=True, callback_closed=True)

        context.run_worker = worker
        actions = {name: Mock(return_value={'eligible_account_created': True})
                   for name in plan.stage_actions.values()}
        if failure:
            with pytest.raises((OSError, RuntimeError)):
                journeys.record_installed_journey(recorder, context, plan, actions=actions)
            assert acknowledged == list(plan.stages[:plan.stages.index(boundary)])
            assert recorder.records[0]['failures']
        else:
            journeys.record_installed_journey(recorder, context, plan, actions=actions)
            assert acknowledged == list(plan.stages)
            steps = recorder.records[0]['steps']
            expected_steps = ['setup', 'start', 'step-1', 'step-2']
            if plan is parent_discovery.PLAN:
                expected_steps.append('step-3')
                actions['create-account'].assert_called_once()
            elif plan is parent_discovery.EMPTY_PLAN:
                expected_steps.append('step-3')
                actions['prepare-empty'].assert_called_once()
            assert [s['step_id'] for s in steps] == [*expected_steps, 'end']
            assert all(s['outcome'] == 'passed' for s in steps)
            assert steps[-2]['assertion_ids'] == ['visible-result']
        assert recorder._active is None
        setup.assert_not_called()
        journeys.Transport.return_value.reboot.assert_not_called()
        assert boot.read.call_args_list and all(call.args == ('boot',) for call in boot.read.call_args_list)


def test_invalid_phase_plan_refuses_before_credentials_or_worker(tmp_path):
    context = SimpleNamespace(credentials=Mock(), run_worker=Mock())
    with pytest.raises(EvidenceError, match='phase-plan'):
        journeys.record_installed_journey(Mock(), context, replace(SYNTHETIC, phases={}))
    context.credentials.provision.assert_not_called()
    context.run_worker.assert_not_called()


@pytest.mark.parametrize('snapshot', [None, ''])
def test_missing_snapshot_refuses_without_installation_or_setup_reply(tmp_path, monkeypatch, snapshot):
    setup = Mock()
    transport = Mock()
    monkeypatch.setattr(installed_setup, 'InstalledSetup', setup)
    monkeypatch.setattr(journeys, 'Transport', transport)
    context = SimpleNamespace(directory=tmp_path, installed_snapshot=snapshot)
    journey = journeys.InstalledJourney(context, Mock(), SYNTHETIC)
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(
            json.dumps({'stage': stage, 'screenshot': None}))
    journey.step(Mock())
    with pytest.raises(EvidenceError, match='installed-snapshot-required'):
        journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(Mock())
    setup.assert_not_called()
    transport.assert_not_called()
    assert not (tmp_path / 'setup-detached.reply.json').exists()


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
    monkeypatch.setattr(journeys, "ReadOnlyObservations", Mock(return_value=SimpleNamespace(
        read=Mock(return_value={"boot_sha256": "b" * 64}))))
    context = SimpleNamespace(directory=directory, host_key="fixture-key", commands=Mock(),
        installed_snapshot='onpc-v1.1',
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


@pytest.mark.parametrize('fault', ['changed', 'missing', 'missing-earlier'])
def test_discovery_comparison_failure_blocks_fixture_and_reply(tmp_path, fault):
    plan = parent_discovery.PLAN
    action, progress = Mock(), Mock()
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), progress, plan,
                                        actions={'create-account': action})
    stage = 'fixture-requested'
    journey.steps = [{'stage': name} for name in plan.stages[:plan.stages.index(stage)]]
    earlier = journeys.SettingsObservation('existing-fixture-child', False, ('0 minutes',))
    if fault != 'missing-earlier': journey.settings_observations['parent-selected'] = earlier
    result = {'operation': 'discovery-ready', 'outcome': 'passed', 'interface': 'AT-SPI'}
    if fault != 'missing':
        result['settings'] = {'child': earlier.child, 'limit_enabled': fault == 'changed',
                              'allowance': ['0 minutes']}
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'a' * 64}))
    journey.ui = SimpleNamespace(observe=Mock(return_value=result))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    with pytest.raises(EvidenceError): journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    action.assert_not_called()
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('fault', [None, 'missing', 'reused', 'reordered', 'wrong-operation'])
@pytest.mark.parametrize('plan', [parent_discovery.PLAN, parent_discovery.EMPTY_PLAN, parent_access.PLAN,
                                 parent_about.PLAN],
                         ids=['discovery', 'empty', 'standard-access', 'about'])
def test_consumers_require_all_fresh_ordered_semantic_results(tmp_path, monkeypatch, fault, plan):
    details, observations = [], []
    for stage, tag in plan.screen_tags.items():
        if tag.startswith('ui:'):
            observations.append({'stage': stage, 'ui': {
                'operation': tag[3:], 'outcome': 'passed', 'interface': 'AT-SPI'}})
        else:
            details.append({'needle': tag, 'result': 'ok',
                            'area': [{'result': 'ok', 'similarity': 100}], 'screenshot': 'safe.png'})
        details.append({'title': plan.prefix + '-' + stage, 'result': 'ok'})
    if fault == 'missing': observations.pop()
    if fault == 'reused': observations[-1] = observations[-2]
    if fault == 'reordered': details[-1], details[-2] = details[-2], details[-1]
    if fault == 'wrong-operation': observations[-1]['ui']['operation'] = 'parent-selected'
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
    monkeypatch.setattr(journeys, 'screenshot', lambda *_: {'sha256': 'a' * 64})
    if fault:
        with pytest.raises(EvidenceError): journeys.matched_screens(tmp_path, plan, observations)
    else:
        assert len(journeys.matched_screens(tmp_path, plan, observations)) == len(plan.screen_tags)
