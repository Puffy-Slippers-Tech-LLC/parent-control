"""Real installed recorder with checked collector sync calls; no VM operations."""

from dataclasses import replace
import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import evidence
import installed_journey as journeys
import installed_setup
import parent_about
import parent_information
import real_interval_qualification
import parent_access
import session_control
import restricted_station_about
import mate_prompt
import kiosk_multiple
import kiosk_approval
import auth_result
import kiosk_approved_flow
import kiosk_rejection
import approval_flow




@pytest.mark.parametrize('cancelled', [False, True])
@pytest.mark.parametrize('diagnostics_fail', [False, True])
def test_step_preserves_failure_and_skips_diagnostics_on_cancellation(cancelled, diagnostics_fail):
    # Transport/lease doubles only; no new process, bus or artifact owner.
    journey = object.__new__(journeys.InstalledJourney)
    journey.plan = SimpleNamespace(prefix='fixture')
    journey.failed = False
    failure = KeyboardInterrupt() if cancelled else RuntimeError('original workflow failure')
    journey._step = Mock(side_effect=failure)
    journey.collect_failure = Mock(side_effect=RuntimeError('diagnostics unavailable')
                                   if diagnostics_fail else None)
    with pytest.raises(type(failure)) as caught:
        journey.step(Mock())
    assert caught.value is failure and journey.failed
    assert journey.collect_failure.call_count == (0 if cancelled else 1)
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(Mock())
    assert journey._step.call_count == 1


def test_failure_collection_is_bounded_to_one_attempt():
    journey = object.__new__(journeys.InstalledJourney)
    journey.context = SimpleNamespace(lease=SimpleNamespace(guard=Mock()))
    journey.plan = SimpleNamespace(prefix='fixture')
    journey.transport = Mock()
    journey.transport.call.return_value = b'oh-no-parent-control:x:1005:1005::/home/oh-no-parent-control:/usr/sbin/nologin\n'
    journey.collect_failure()
    journey.collect_failure()
    assert journey.transport.call.call_count == journey.context.lease.guard.call_count == 5
    assert journey.transport.call.call_args.args[0] == journeys.kiosk_journal_command('1005')


def test_failure_journal_matches_the_kiosk_and_root_reports_about_it():
    # journalctl ANDs different fields, ORs values of one field, and '+'
    # separates alternatives. Exercise that semantics rather than argv shape.
    arguments = journeys.kiosk_journal_command('1005')[5:]
    branches = [[]]
    for argument in arguments:
        if argument == '+':
            branches.append([])
        else:
            branches[-1].append(argument.split('=', 1))

    def matches(entry):
        return any(all(entry.get(field) in [value for key, value in branch if key == field]
                       for field in {key for key, _ in branch}) for branch in branches)

    unit = 'oh-no-parent-control-polkit-agent.service'
    for uid in ('0', '1000', '1005'):
        assert matches({'_UID': uid, '_SYSTEMD_USER_UNIT': unit}) == (uid == '1005')
        assert matches({'_UID': uid, 'USER_UNIT': unit}) == (uid == '1005')
        assert matches({'_UID': '0', 'OBJECT_UID': uid,
                        'OBJECT_SYSTEMD_USER_UNIT': unit}) == (uid == '1005')
        assert matches({'_UID': '0', 'COREDUMP_UID': uid,
                        'COREDUMP_USER_UNIT': unit}) == (uid == '1005')
    assert not matches({'_UID': '1005', '_SYSTEMD_USER_UNIT': 'unrelated.service'})
    for uid in ('0', '1000', '1005'):
        assert matches({'_UID': uid, '_SYSTEMD_USER_UNIT':
                        'gnome-session-manager@oh-no-parent-control.service'}) == (uid == '1005')
        assert matches({'_UID': uid, '_COMM': 'gnome-session'}) == (uid == '1005')
    assert not matches({'_UID': '1005', '_COMM': 'unrelated'})


@pytest.mark.parametrize('failure', [0, 1])
def test_flow07_selector_runs_separate_owned_attempts_and_stops_after_failure(monkeypatch, failure):
    import check_e2e_approval_flow as selector
    smoke = Mock(side_effect=[failure, 0])
    monkeypatch.setattr(selector, 'smoke', smoke)
    monkeypatch.setattr(selector, 'named_input', lambda: 'owned-input')
    assert selector.main() == failure
    assert [call.kwargs for call in smoke.call_args_list] == [
        dict(assets='owned-input', provision_credentials=True, approval_flow=outcome)
        for outcome in (('rejection',) if failure else ('rejection', 'cancel'))]
import restricted_station


@pytest.mark.parametrize('selector,mode', [('auth_prompt', 'mate_prompt'),
                                          ('read_restricted_station_about', 'restricted_station_about'),
                                          ('kiosk_multiple', 'kiosk_multiple'),
                                          ('kiosk_approval', 'kiosk_approval'),
                                          ('baseline_auth_pause', 'baseline_auth_pause'),
                                          ('auth_result', 'auth_result'),
                                          ('kiosk_approved_flow', 'kiosk_approved_flow'),
                                          ('kiosk_rejection', 'kiosk_rejection')])
def test_auth_prompt_qualification_reuses_owned_mate_envelope(selector, mode):
    # The argument-free selector must not acquire a separate VM/cleanup route.
    import ast
    source = (ROOT / ('tests/integration/check_e2e_' + selector + '.py')).read_text()
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'smoke']
    assert len(calls) == 1
    keywords = {item.arg: ast.unparse(item.value) for item in calls[0].keywords}
    assets = ('named_input(package_source=True)' if selector in (
        'kiosk_approval', 'kiosk_approved_flow', 'baseline_auth_pause')
              else 'named_input()')
    assert keywords == {'assets': assets, 'provision_credentials': 'True',
                        mode: 'True'}
import kiosk_no_child
import kiosk_no_approver
import catalogue
from match_rules import MatchRuleJourney
import retained_parent
import allowance
import time_explanation


@pytest.mark.parametrize('fault', ['', 'grant', 'settings', 'clock', 'missing', 'replay'])
def test_revoke_cancel_real_step_preserves_checks_before_durable_reply(tmp_path, fault):
    # Existing private files/recorders only; no new process, bus or cleanup owner.
    from copy import deepcopy
    from time_explanation import RevokeCancelJourney, REVOKE_PLAN
    journey = RevokeCancelJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.grant_estimate = {'estimate': {'seconds': 975}, 'observed_monotonic_ns': 1}
    value = {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['15 minutes']},
        'balances': {'child': 'fixture-child', 'expanded': True, 'observed_monotonic_ns': 1_000_000_000,
            **{key: {'text': text, 'seconds': seconds, 'precision_seconds': 1}
               for key, text, seconds in (('daily', '15m', 900), ('one_time', '16m 15s', 975),
                                          ('total', '16m 15s', 975))}},
        'read_bounds': [1_000_000_000, 2_000_000_000]}
    if fault != 'missing': journey.check_settings('before', {'ui': {'revoke_cancel': value}})
    current = deepcopy(value)
    current['read_bounds'] = [3_000_000_000, 4_000_000_000]
    current['balances']['observed_monotonic_ns'] = 3_000_000_000
    if fault == 'grant': current['balances']['one_time']['seconds'] = 0
    if fault == 'settings': current['settings']['allowance'] = ['30 minutes']
    if fault == 'clock': current['read_bounds'] = [1, 2]
    if fault == 'replay': journey.check_settings('first-balances', {'ui': {'revoke_cancel': current}})
    # A caller mutation cannot rewrite the stored baseline.
    value['settings']['allowance'].clear()
    stage = 'first-balances'
    journey.steps = [{'stage': s} for s in REVOKE_PLAN.stages[:REVOKE_PLAN.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'revoke-balances', 'outcome': 'passed', 'revoke_cancel': current}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert journey.failed and not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['comparison']['unchanged_balances_with_elapsed_bounds']
@pytest.mark.parametrize('fault', ['', 'grant', 'daily', 'total', 'settings', 'apps', 'rules',
                                   'clock', 'missing', 'replay'])
def test_revocation_real_step_requires_cleared_grant_and_unchanged_saved_policy(tmp_path, fault):
    from copy import deepcopy
    from time_explanation import RevokeConfirmJourney, REVOKE_CONFIRM_PLAN
    journey = RevokeConfirmJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.grant_estimate = {'estimate': {'seconds': 975}, 'observed_monotonic_ns': 1}
    value = {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['15 minutes']},
        'apps': [['parent-app-0000000000000000', 'conditional', 'pattern']],
        'rules': [['parent-app-0000000000000000', '/opt/fixture/*']],
        'balances': {'child': 'fixture-child', 'expanded': True, 'observed_monotonic_ns': 1_000_000_000,
            **{key: {'text': text, 'seconds': seconds, 'precision_seconds': 1}
               for key, text, seconds in (('daily', '15m', 900), ('one_time', '16m 15s', 975),
                                          ('total', '16m 15s', 975))}},
        'read_bounds': [1_000_000_000, 2_000_000_000]}
    if fault != 'missing': journey.check_settings('before', {'ui': {'revoke_cancel': value}})
    current = deepcopy(value)
    current['read_bounds'] = [3_000_000_000, 4_000_000_000]
    current['balances']['observed_monotonic_ns'] = 3_000_000_000
    current['balances']['one_time'] = {'text': '0m', 'seconds': 0, 'precision_seconds': 1}
    current['balances']['total'] = deepcopy(current['balances']['daily'])
    if fault == 'grant': current['balances']['one_time']['seconds'] = 1
    if fault == 'daily': current['balances']['daily']['seconds'] = 850
    if fault == 'total': current['balances']['total']['seconds'] = 975
    if fault == 'settings': current['settings']['allowance'] = ['30 minutes']
    if fault == 'apps': current['apps'][0][1] = 'permanent'
    if fault == 'rules': current['rules'][0][1] = '/opt/other/*'
    if fault == 'clock': current['read_bounds'] = [1, 2]
    if fault == 'replay': journey.check_settings('after', {'ui': {'revoke_cancel': current}})
    value['settings']['allowance'].clear()
    value['apps'].clear()
    value['rules'].clear()
    stage = 'after'
    journey.steps = [{'stage': s} for s in REVOKE_CONFIRM_PLAN.stages[:REVOKE_CONFIRM_PLAN.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'revoke-cleared-balances', 'outcome': 'passed', 'revoke_cancel': current}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert journey.failed and not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert journey.steps[-1]['comparison']['grant_cleared']
        assert journey.steps[-1]['comparison']['unchanged_app_rules']


def test_revocation_comparisons_allow_independent_caller_endpoints(tmp_path):
    from copy import deepcopy
    from request_composition import RevocationJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='independent', worker_mode='revocation',
        screen_tags={'decision': 'ui:kiosk-valid-fraction-soft-read',
                     'capture': 'ui:revoke-saved-balances', 'result': 'ui:revoke-cleared-balances'},
        phases={'ready': 'setup', 'decision': 'step-1', 'capture': 'step-1', 'result': 'step-1'})
    journey = RevocationJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
        read_checks={'capture': (None, 'confirm'), 'result': ('capture', 'confirm')},
        window_checks={}, approval_stage='decision')
    journey.balance = {'observed_monotonic_ns': 1,
                      'daily': {'seconds': 900, 'precision_seconds': 1},
                      'one_time': {'seconds': 0, 'precision_seconds': 1}}
    choice = {'estimate': {'kind': 'fixed', 'seconds': 975},
              'request': {'duration_seconds': 75}, 'observed_monotonic_ns': 1}
    journey.check_settings('decision', {'ui': {'valid_choice': choice}})
    choice['estimate']['seconds'] = 1  # Capturing cannot retain mutable decoder data.
    value = {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['15 minutes']},
        'apps': [], 'rules': [], 'read_bounds': [1_000_000_000, 2_000_000_000],
        'balances': {'observed_monotonic_ns': 1_000_000_000,
            **{key: {'seconds': seconds, 'precision_seconds': 1}
               for key, seconds in (('daily', 900), ('one_time', 975), ('total', 975))}}}
    journey.check_settings('capture', {'ui': {'revoke_cancel': value}})
    current = deepcopy(value)
    current['read_bounds'] = [3_000_000_000, 4_000_000_000]
    current['balances']['one_time']['seconds'] = 0
    current['balances']['total']['seconds'] = 900
    observed = {'ui': {'revoke_cancel': current}}
    journey.check_settings('result', observed)
    assert observed['comparison']['grant_cleared']


@pytest.mark.parametrize('fault', ['', 'window', 'missing', 'replay', 'plan'])
def test_revocation_retained_window_uses_caller_endpoints_and_immutable_capture(tmp_path, fault):
    from request_composition import RevocationJourney
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='independent', worker_mode='revocation',
        screen_tags={'leaving': 'ui:retained-parent-leave',
                     'returning': 'ui:retained-parent-read'},
        phases={'ready': 'setup', 'leaving': 'step-1', 'returning': 'step-1'})
    if fault == 'plan':
        with pytest.raises(EvidenceError, match='revocation:window-plan'):
            RevocationJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
                read_checks={}, window_checks={'leaving': 'returning'}, approval_stage=None)
        return
    journey = RevocationJourney(SimpleNamespace(directory=tmp_path), Mock(), plan,
        read_checks={}, window_checks={'returning': 'leaving'}, approval_stage=None)
    original = {'window': {'pid': 101, 'object_path': '/public/window'},
                'page': 'Screen Limits', 'settings': {'child': 'fixture-child'}}
    expected = copy.deepcopy(original)
    if fault != 'missing':
        journey.check_settings('leaving', {'ui': {'retained_parent': original}})
    original['window']['pid'] = 202
    if fault == 'window': expected['window']['pid'] = 303
    if fault == 'replay':
        with pytest.raises(EvidenceError, match='revoke-cancel:read-replay'):
            journey.check_settings('leaving', {'ui': {'retained_parent': original}})
    elif fault:
        with pytest.raises(EvidenceError, match='revoke-cancel:retained-parent'):
            journey.check_settings('returning', {'ui': {'retained_parent': expected}})
    else:
        journey.check_settings('returning', {'ui': {'retained_parent': expected}})


import parent_discovery
import shell_search_results
import parent_search_launch
import license_viewer_provider
import shell_search
import inventory
from private_artifacts import EvidenceError, PrivateCollector
from recording import ScenarioRecorder
from tests.support.paths import ROOT
from tests.support.e2e_recording import collector_sync


SYNTHETIC = journeys.JourneyPlan(
    prefix='example', worker_mode='example_view',
    screen_tags={'installed-greeter': 'ui:gdm-list', 'opened': 'ui:parent-window',
                 'details': 'ui:parent-about', 'returned': 'ui:parent-window'},
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            'opened': 'step-1', 'details': 'step-1', 'returned': 'step-2'},
    advance_after={'details': 'step-2'},
)

INTERVAL_RECORDER_PLAN = replace(real_interval_qualification.PLAN,
    advance_after={'before': 'step-2'},
    phases={**real_interval_qualification.PLAN.phases, 'after': 'step-2'})


@pytest.mark.parametrize('tag', ['onpc-example-pixels', 'screenshot:parent',
                               'geometry:control', 'ui:', None])
def test_customer_plan_refuses_image_or_geometry_acceptance_before_execution(tag):
    with pytest.raises(EvidenceError, match='semantic-plan'):
        replace(SYNTHETIC, screen_tags={'opened': tag})


@pytest.mark.parametrize('observed', [True, False])
def test_semantic_results_do_not_depend_on_graphical_diagnostics(tmp_path, observed):
    plan = replace(SYNTHETIC, screen_tags={'opened': 'ui:parent-window'})
    (tmp_path / 'testresults').mkdir()
    # An optional backend diagnostic has no image/geometry authority. In
    # particular it cannot require reading an absent screenshot or replace a
    # missing independent product result, even with a perfect match score.
    details = [{'needle': 'unrelated-desktop', 'result': 'ok',
                'area': [{'result': 'ok', 'similarity': 17 if observed else 100}],
                'screenshot': 'missing.png'},
               {'title': 'example-opened', 'result': 'ok'}]
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps({
        'result': 'ok', 'details': details}))
    observations = [{'stage': 'opened', 'ui': {
        'operation': 'parent-window', 'outcome': 'passed'}}] if observed else []
    if observed:
        assert journeys.matched_screens(tmp_path, plan, observations) == [{
            'stage': 'opened', 'detail_index': 1, 'ui': observations[0]['ui']}]
    else:
        with pytest.raises(EvidenceError, match='ui-evidence'):
            journeys.matched_screens(tmp_path, plan, observations)


@pytest.fixture
def journey_inventory():
    # Read-only template: each case copies only its family before mutation.
    # Avoid writing the entire customer catalogue for every recorder fault.
    return inventory.read_json(ROOT / 'tests/e2e/scenarios.json')[0]


def test_shared_system_prompt_coordinate_rendezvous_refuses_before_files_or_guard(tmp_path):
    journey = journeys.InstalledJourney(
        SimpleNamespace(directory=tmp_path), Mock(), parent_access.PLAN)
    guard = Mock(side_effect=AssertionError('guard must not run'))
    with pytest.raises(EvidenceError, match='prompt-coordinate-route-refused'):
        journey.dismiss_system_prompt('app-grid', {'x': 200, 'y': 330}, guard)
    guard.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('fault', [None, 'missing', 'wrong-token', 'guard'])
def test_custom_batch_receipt_precedes_result_and_refuses_missing_or_foreign_input(tmp_path, monkeypatch, fault):
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), parent_access.PLAN)
    clock = [0.0]
    monkeypatch.setattr(journeys.time, 'monotonic', lambda: clock[0])
    def advance(_seconds):
        clock[0] += 30
        if fault != 'missing':
            (tmp_path / 'rapid.input-done.json').write_text(json.dumps({
                'stage': 'rapid', 'token': ('b' if fault == 'wrong-token' else 'a') * 32}))
    monkeypatch.setattr(journeys.time, 'sleep', advance)
    guard = Mock(side_effect=RuntimeError('lost worker') if fault == 'guard' else None)
    if fault:
        with pytest.raises((EvidenceError, RuntimeError)):
            journey.wait_trace_input('rapid', 'a' * 32, guard)
    else:
        journey.wait_trace_input('rapid', 'a' * 32, guard)
        assert clock[0] == 30
    assert guard.called
    assert clock[0] <= 60


@pytest.mark.parametrize('operation', ['desktop', 'fresh-parent-desktop', 'standard-desktop',
                                       'fresh-standard-desktop', 'parent-selected'])
@pytest.mark.parametrize('fault', [None, 'ui', 'boot', 'preparation'])
def test_parent_desktop_preparation_is_shared_durable_and_fail_closed(
        tmp_path, monkeypatch, operation, fault):
    plan = replace(SYNTHETIC, screen_tags={'entry': 'ui:' + operation},
                   phases={'ready': 'setup', 'setup-detached': 'setup', 'entry': 'step-1'},
                   advance_after={})
    progress = Mock()
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
    journey.boot = 'a' * 64
    journey.transport = object()
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    journey.ui = SimpleNamespace(
        boot_proof=('b' if fault == 'boot' else 'a') * 64,
        observe=Mock(return_value=result, side_effect=RuntimeError('ui-failed') if fault == 'ui' else None))
    preparation = {'operation': 'parent-continuous-activity', 'outcome': 'passed',
                   'interface': 'system session', 'idle_delay_seconds': 0,
                   'previous_idle_delay_seconds': 300}
    prepare = Mock(return_value=preparation,
                   side_effect=RuntimeError('prepare-failed') if fault == 'preparation' else None)
    monkeypatch.setattr(session_control, 'observe', prepare)
    (tmp_path / 'entry.request.json').write_text(json.dumps({'stage': 'entry', 'screenshot': None}))
    parent = operation in ('desktop', 'fresh-parent-desktop')
    if fault in ('ui', 'boot') or fault == 'preparation' and parent:
        with pytest.raises((RuntimeError, EvidenceError)):
            journey.step(Mock())
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
        progress.assert_not_called()
        assert not (tmp_path / 'entry.reply.json').exists()
    else:
        def recorded(stage, observed):
            assert stage == 'entry'
            assert not (tmp_path / 'entry.reply.json').exists()
            assert observed.get('desktop_preparation') == (preparation if parent else None)
        progress.side_effect = recorded
        journey.step(Mock())
        progress.assert_called_once()
        assert (tmp_path / 'entry.reply.json').exists()
    if parent and fault not in ('ui', 'boot'):
        prepare.assert_called_once_with(journey.transport, 'parent-continuous-activity')
    else:
        prepare.assert_not_called()


@pytest.mark.parametrize('failure', [
    None, 'observation-write', 'return-step-write', 'assertion-write', 'worker-loss',
])
def test_shared_recorder_commits_before_reply_and_latches_failure(
        tmp_path, monkeypatch, journey_inventory, collector_sync, failure):
    # One independent plan exercises recorder integrity. Product scenarios own
    # their own actions/results; adding a consumer must not enlarge this test.
    plan = replace(SYNTHETIC, assertions_after={'details': 'visible-result'})
    selector = 'E2E-030/parent'
    scenario = copy.deepcopy(next(
        item for item in journey_inventory['scenarios'] if item['id'] == 'E2E-030'))
    selected = next(item for item in scenario['variants'] if item['id'] == 'parent')
    selected.update(status='ready', pending_reason=None,
                    executable={'path': 'tests/e2e/installed_journey.py',
                                'test_id': 'synthetic-recorder-safety'})
    scenario['assertions']['visible'] = [
        {'id': 'visible-result', 'step_id': 'step-1', 'description': 'Independent return.'}]
    document = {**journey_inventory, 'scenarios': [scenario]}
    inventory_path = tmp_path / 'scenarios.json'
    inventory_path.write_text(json.dumps(document))
    inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in evidence.INPUT_FIELDS}
    inputs.update(inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
                  environment_id='ubuntu26-04-pinned')
    contract = evidence.EvidenceContract(inventory_path=inventory_path, root=ROOT,
        selector=selector, run_id='shared-controller-test', inputs=inputs)
    directory = tmp_path / 'raw'
    directory.mkdir()
    (directory / 'testresults').mkdir()
    details = [{'title': plan.prefix + '-' + stage, 'result': 'ok'}
               for stage in plan.screen_tags]
    (directory / 'testresults/result-smoke.json').write_text(
        json.dumps({'result': 'ok', 'details': details}))
    monkeypatch.setattr(journeys.system, 'address', Mock(return_value='fixture-host'))
    monkeypatch.setattr(journeys, 'Transport', Mock())
    setup, provision = Mock(), Mock()
    monkeypatch.setattr(installed_setup, 'InstalledSetup',
                        Mock(return_value=SimpleNamespace(run=setup, provision=provision)))
    monkeypatch.setattr(journeys, 'ReadOnlyObservations', Mock())
    monkeypatch.setattr(journeys, 'UiObservations', Mock(return_value=SimpleNamespace(
        boot_proof='b' * 64, observe=lambda operation: {
            'operation': operation, 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider'})))
    context = SimpleNamespace(directory=directory, host_key='fixture-key', commands=Mock(),
        installed_snapshot='onpc-v9.8.7', guestfs=Mock(), credentials=Mock(),
        verified=SimpleNamespace(inputs=inputs),
        lease=SimpleNamespace(source=SimpleNamespace(uuid='fixture-uuid'),
            capture=SimpleNamespace(state={'guest': {'fixture_boundary': 'legacy'}}),
            view=SimpleNamespace(domain_id=7), state={'run': 'a' * 32}, guard=Mock()))
    boundary = 'details'
    state = {'stage': None, 'stored': False}

    with PrivateCollector(run_id=contract.run_id, secrets=[], parent=tmp_path) as collector:
        recorder = ScenarioRecorder(contract, collector)
        recorder.begin_case(selector)
        save = collector.save_report

        def checkpoint(name, value):
            if state['stage'] == boundary and (
                    failure == 'observation-write' and value.get('event') == 'observation'
                    or failure == 'return-step-write' and value.get('event') == 'step-started'
                    and value['active_step'] == 'step-2'
                    or failure == 'assertion-write' and value.get('event') == 'assertion'):
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
            for stage in plan.stages:
                state.update(stage=stage, stored=False)
                (directory / (stage + '.request.json')).write_text(
                    json.dumps({'stage': stage, 'screenshot': None}))

                def guard():
                    assert not (directory / (stage + '.reply.json')).exists()
                    if failure == 'worker-loss' and stage == boundary and state['stored']:
                        raise RuntimeError('fixed worker loss')
                    return 1800.0

                try:
                    options['guarded_observe'](guard)
                except (OSError, RuntimeError):
                    assert not (directory / (stage + '.reply.json')).exists()
                    with pytest.raises(EvidenceError, match='previous-failure'):
                        options['guarded_observe'](Mock())
                    raise
                assert state['stored']
                assert (directory / (stage + '.reply.json')).exists()
                assert recorder._active['step_id'] == plan.advance_after.get(stage, plan.phases[stage])
                acknowledged.append(stage)
            assert [item['stage'] for item in options['validate']()] == list(plan.screen_tags)
            return dict(outcome='passed', shutdown_verified=True,
                        worker_stopped=True, callback_closed=True)

        context.run_worker = worker
        if failure:
            with pytest.raises((OSError, RuntimeError)):
                journeys.record_installed_journey(recorder, context, plan)
            assert acknowledged == list(plan.stages[:plan.stages.index(boundary)])
            assert recorder.records[0]['failures']
        else:
            journeys.record_installed_journey(recorder, context, plan)
            assert acknowledged == list(plan.stages)
            record = recorder.records[0]
            assert [step['step_id'] for step in record['steps']] == [
                'setup', 'start', 'step-1', 'step-2', 'end']
            assert all(step['outcome'] == 'passed' for step in record['steps'])
            assert [(item['assertion_id'], item['step_id']) for item in record['assertions']] == [
                ('visible-result', 'step-1')]
        assert recorder._active is None
        setup.assert_not_called()
        provision.assert_called_once()
        journeys.Transport.return_value.reboot.assert_not_called()


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


@pytest.mark.parametrize('failure', [False, True])
def test_legacy_dormant_install_guard_preserves_setup_before_customer_input(tmp_path, monkeypatch, failure):
    setup = Mock()
    setup.return_value.run.return_value = {'setup_reboot_verified': True, 'package_verified': False}
    if failure:
        setup.return_value.run.side_effect = EvidenceError('installation-failed')
    monkeypatch.setattr(installed_setup, 'InstalledSetup', setup)
    monkeypatch.setattr(journeys, 'Transport', Mock())
    monkeypatch.setattr(journeys, 'ReadOnlyObservations', Mock())
    monkeypatch.setattr(journeys.system, 'address', lambda *_args, **_kwargs: '192.0.2.1')
    context = SimpleNamespace(directory=tmp_path, install_current_package=True,
                              lease=Mock(), verified=Mock(), commands=Mock(), host_key='test-key')
    context.lease.state = {'run': 'test-run'}
    context.lease.capture.state = {'guest': {'fixture_boundary': 'legacy'}}
    context.verified.fixture_prepared = None
    journey = journeys.InstalledJourney(context, Mock(), SYNTHETIC)
    guard = Mock()
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(
            json.dumps({'stage': stage, 'screenshot': None}))
    journey.step(guard)
    if failure:
        with pytest.raises(EvidenceError, match='installation-failed'):
            journey.step(guard)
        assert not (tmp_path / 'setup-detached.reply.json').exists()
    else:
        journey.step(guard)
        assert json.loads((tmp_path / 'setup-detached.reply.json').read_text()) == {'setup_complete': True}
    setup.return_value.run.assert_called_once_with(guard, verify=False)
    setup.return_value.provision.assert_not_called()


@pytest.mark.parametrize('binding,failure', [('activity', False), ('activity', True), ('policy', False)])
def test_activity_consumer_verifies_baseline_before_setup_reply(tmp_path, monkeypatch, binding, failure):
    import native_fixtures
    setup, transport, fixtures = Mock(), Mock(), Mock()
    if failure:
        fixtures.return_value.verify.side_effect = EvidenceError('native:activity-not-ready')
    monkeypatch.setattr(installed_setup, 'InstalledSetup', setup)
    monkeypatch.setattr(journeys, 'Transport', transport)
    monkeypatch.setattr(journeys, 'ReadOnlyObservations', Mock())
    monkeypatch.setattr(journeys.system, 'address', lambda *_args, **_kwargs: '192.0.2.1')
    monkeypatch.setattr(native_fixtures, 'NativeFixtures', fixtures)
    tag = 'ui:overlay-native-activity-launch' if binding == 'activity' else 'ui:native-command-launch'
    plan = replace(SYNTHETIC, screen_tags={'activity-command': tag},
                   phases={'ready': 'setup', 'setup-detached': 'setup', 'activity-command': 'step-1'})
    context = SimpleNamespace(directory=tmp_path, installed_snapshot='accepted-snapshot',
                              lease=Mock(), verified=Mock(), commands=Mock(), host_key='test-key')
    context.lease.state = {'run': 'test-run'}
    context.lease.capture.state = {'guest': {'fixture_boundary': 'legacy'}}
    context.verified.fixture_prepared = None
    journey = journeys.InstalledJourney(context, Mock(), plan)
    guard = Mock()
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(
            json.dumps({'stage': stage, 'screenshot': None}))
    journey.step(guard)
    if failure:
        with pytest.raises(EvidenceError, match='native:activity-not-ready'): journey.step(guard)
        assert not (tmp_path / 'setup-detached.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(guard)
    else:
        journey.step(guard)
        assert json.loads((tmp_path / 'setup-detached.reply.json').read_text()) == {'setup_complete': True}
    if binding == 'activity':
        fixtures.assert_called_once_with(transport.return_value, context.verified, profile='activity')
        fixtures.return_value.verify.assert_called_once_with()
    else:
        fixtures.assert_not_called()
    setup.return_value.run.assert_not_called()


def test_review_requires_a_named_qualification_mode(tmp_path):
    with pytest.raises(EvidenceError, match='review-mode'):
        journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), Mock(), SYNTHETIC, review=True)


def test_stage_action_runs_after_worker_guard_and_before_durable_reply(tmp_path, monkeypatch):
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock())
    plan = replace(SYNTHETIC, screen_tags={"created": "system:parent-command-context"},
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
    monkeypatch.setattr(journeys.session_control, 'observe', Mock(return_value={
        'operation': 'parent-command-context', 'outcome': 'passed'}))
    context = SimpleNamespace(directory=directory, host_key="fixture-key", commands=Mock(),
        installed_snapshot='onpc-v9.8.7',
        verified=Mock(), lease=SimpleNamespace(source=SimpleNamespace(uuid="fixture-uuid"),
        capture=SimpleNamespace(state={'guest': {'fixture_boundary': 'legacy'}}),
        view=SimpleNamespace(domain_id=7), state={"run": "a" * 32}, guard=Mock()))
    context.verified.fixture_prepared = None
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
    result = {'operation': 'discovery-ready', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    if fault != 'missing':
        result['settings'] = {'child': earlier.child, 'limit_enabled': fault == 'changed',
                              'allowance': ['0 minutes']}
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'a' * 64}))
    journey.ui = SimpleNamespace(boot_proof='a' * 64, observe=Mock(return_value=result))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    with pytest.raises(EvidenceError): journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    action.assert_not_called()
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('fault', ['child', 'toggle', 'allowance', 'missing', 'missing-earlier'])
def test_parent_information_return_comparison_refuses_before_durable_reply(tmp_path, fault):
    plan = parent_information.PLAN
    progress = Mock()
    journey = journeys.InstalledJourney(SimpleNamespace(directory=tmp_path), progress, plan)
    stage = 'parent-returned'
    journey.steps = [{'stage': name} for name in plan.stages[:plan.stages.index(stage)]]
    earlier = journeys.SettingsObservation('fixture-child', False, ('0 minutes',))
    if fault != 'missing-earlier':
        journey.settings_observations['parent-selected'] = earlier
    result = {'operation': 'parent-returned', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    if fault != 'missing':
        result['settings'] = {
            'child': 'existing-fixture-child' if fault == 'child' else earlier.child,
            'limit_enabled': fault == 'toggle',
            'allowance': ['1 hour'] if fault == 'allowance' else ['0 minutes'],
        }
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'a' * 64}))
    journey.ui = SimpleNamespace(boot_proof='a' * 64, observe=Mock(return_value=result))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    category = ('ui:missing-settings-observation' if fault in ('missing', 'missing-earlier')
                else 'ui:settings-changed:' + {'child': 'child', 'toggle': 'limit_enabled',
                                             'allowance': 'allowance'}[fault])
    with pytest.raises(EvidenceError, match=category):
        journey.step(Mock())
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(Mock())
    progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('fault', [None, 'missing', 'reused', 'reordered', 'wrong-operation'])
def test_shared_result_gate_requires_fresh_ordered_semantic_results(tmp_path, fault):
    plan = SYNTHETIC
    details, observations = [], []
    for stage, tag in plan.screen_tags.items():
        if tag.startswith('ui:'):
            observations.append({'stage': stage, 'ui': {
                'operation': tag[3:], 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}})
        elif tag.startswith('system:'):
            observations.append({'stage': stage, 'system': {
                'operation': tag[7:], 'outcome': 'passed', 'interface': 'system session'}})
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
    if fault:
        with pytest.raises(EvidenceError): journeys.matched_screens(tmp_path, plan, observations)
    else:
        assert len(journeys.matched_screens(tmp_path, plan, observations)) == len(plan.screen_tags)
