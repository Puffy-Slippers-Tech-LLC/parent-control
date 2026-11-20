"""Boundary and execution tests for all approved test category routes."""
from tools.test_storage import named_input
from tests.support.vm_registry import vm_name
from dataclasses import replace
from contextlib import nullcontext
import fcntl
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import MagicMock, Mock
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT
from tests.support.launcher import synthetic_package_identity
import test_launcher as host
import test_commands as commands

VM_ARGS = ['--vm', vm_name()]


def test_vm_snapshot_pass_survives_later_checkout_changes(tmp_path, monkeypatch):
    import hashlib
    import threading
    import launcher_reload
    import prepare_appsnapshot
    import regression_process
    import test_activity
    import test_checkpoint
    import test_recovery
    import test_source
    import vm_test_queue
    from tools import test_storage, vm_source_snapshot
    from vm_selection import VARIABLE

    monkeypatch.setattr(os, 'environ', os.environ.copy())
    monkeypatch.setattr(regression_process, 'session_stop', regression_process.session_stop)
    source = tmp_path / 'tools' / 'captured.py'
    source.parent.mkdir()
    source.write_text('original input')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(test_storage, 'scratch_directory', lambda: scratch)
    monkeypatch.setattr(vm_test_queue, '__file__', str(source.parent / 'vm_test_queue.py'))
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda root: dict(
        digest=hashlib.sha256(source.read_bytes()).hexdigest(), generation=0))
    monkeypatch.setattr(vm_test_queue.vm_config, 'select', lambda name: monkeypatch.setenv(VARIABLE, name))
    monkeypatch.setattr(vm_test_queue.vm_config, 'load', lambda name: SimpleNamespace(family='deb'))
    monkeypatch.setattr(prepare_appsnapshot, 'reservation', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(prepare_appsnapshot, 'ensure_snap_prepared', lambda *args: 0)
    monkeypatch.setattr(test_activity, 'activity', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(test_source, 'reader', lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(launcher_reload, 'watching', nullcontext)
    monkeypatch.setattr(test_recovery, 'cleanup', lambda root: 0)
    control = SimpleNamespace(stopped=threading.Event())
    control.installed = lambda **kwargs: nullcontext(control)
    monkeypatch.setattr(vm_test_queue, 'Control', lambda: control)
    # The real worker publishes frames; this private test needs no viewer.
    monkeypatch.setattr(regression_process, 'PipeFrameOutput', lambda stream: SimpleNamespace(
        frame=lambda value: None, write=stream.write, flush=stream.flush))
    monkeypatch.setattr(sys, 'stdout', sys.stdout)
    selection = [('system', ['check_snapshot'])]
    monkeypatch.setattr(commands, 'selections', lambda *args: selection)
    work = dict(category='system', options=['check_snapshot'],
                cases=['check_snapshot'], case='check_snapshot', area=False)
    with test_checkpoint.PassCheckpoint(tmp_path, selection, {'one': 'deb'}, {'deb': [work]}) as shared:
        assignment = shared.claim('deb', 'one', work)
        request = tmp_path / 'work.json'
        request.write_text(json.dumps(dict(selection=['system', 'check_snapshot'],
            passed={'system': []}, assignment=assignment)))
        monkeypatch.setenv(vm_test_queue.FAMILY_WORK, str(request))

        def execute(args, *, detached, checkpoint):
            with vm_source_snapshot.capture(tmp_path):
                source.write_text('incoming change')
                assert vm_source_snapshot.read_bytes(source) == b'original input'
                checkpoint.event('system', dict(kind='finished', nodeid='check_snapshot'), set())
                checkpoint.queue_finalized = True
            return 0

        monkeypatch.setattr(commands, '_main', execute)
        assert vm_test_queue.worker(['--execute', 'one', 'system', 'check_snapshot']) == 0
        evidence = test_checkpoint.Checkpoint.worker_result(tmp_path, 'one')
        assert shared.accept(assignment, evidence, 0)
        assert source.read_text() == 'incoming change'
        shared.retry('deb', 'check_snapshot')
        assignment = shared.claim('deb', 'one', work)
        request.write_text(json.dumps(dict(selection=['system', 'check_snapshot'],
            passed={'system': []}, assignment=assignment)))
        monkeypatch.setenv(vm_test_queue.FAMILY_WORK, str(request))
        monkeypatch.setattr(vm_test_queue, 'reservation', lambda *args, **kwargs: nullcontext())
        recoveries = []
        monkeypatch.setattr(test_recovery, 'cleanup',
                            lambda root: recoveries.append(control.stopped.is_set()) or 0)
        monkeypatch.setattr(commands, '_main', lambda *args, **kwargs: pytest.fail('cancelled test started'))
        control.stopped.set()
        assert vm_test_queue.worker(['--execute', 'one', 'system', 'check_snapshot']) == 130
        evidence = test_checkpoint.Checkpoint.worker_result(tmp_path, 'one')
        assert recoveries == [False] and evidence['cleanup'] and evidence['interrupted']
        assert evidence['assignment'] == assignment['assignment'] and not evidence['passed']
        assert not shared.accept(assignment, evidence, 130, interrupted=True)
        assert list(shared.pending('deb')) == [work]


def test_plain_goal_session_waits_for_native_completion(tmp_path, monkeypatch):
    import agent_adapter
    import agent_codex
    import detached_launcher

    adapter = agent_codex.CodexAdapter()
    monkeypatch.setattr(adapter, 'prepare_environment', lambda root, environment: environment)
    monkeypatch.setattr(adapter, 'executable', lambda environment: '/unused/codex')
    monkeypatch.setattr(detached_launcher, 'prepare_session', adapter.prepare_session)
    selection = agent_adapter.AgentSelection('codex', tmp_path)
    command = detached_launcher.agent_command(tmp_path, 'gpt-6.1-sol', 'high', tmp_path,
                                               selection=selection)
    assert command.request.schema is None
    assert 'app-server' in command.argv and '--output-schema' not in command.argv
    assert not hasattr(command.protocol, 'finalize_result')
    with pytest.raises(ValueError, match='fresh native thread'):
        command.revised(thread_id='old-thread')

    (tmp_path / 'prompt.txt').write_text('Investigate, fix, validate and finish required Git work.')
    renderer = Mock()
    # Reporting failure cannot kill the actual repair session or change its
    # lifecycle verdict. Protocol errors are outside this optional boundary.
    renderer.event.side_effect = OSError('optional transcript unavailable')
    session = detached_launcher._GoalSession(command, tmp_path, renderer,
        dict(session='test-session', status='running', started_at=0))
    native = command.protocol

    def take():
        packets = [json.loads(line) for line in native.outgoing.splitlines()]
        native.outgoing.clear()
        return packets

    def feed(packet):
        session.feed((json.dumps(packet) + '\n').encode())

    assert take()[0]['method'] == 'initialize'
    feed({'id': 1, 'result': {}})
    started = take()[-1]
    assert started['method'] == 'thread/start'
    assert started['params']['sandbox'] == 'workspace-write'
    feed({'id': started['id'], 'result': {'thread': {'id': 'fresh'}}})
    turn = take()[0]
    assert turn['method'] == 'turn/start' and 'outputSchema' not in turn['params']
    feed({'id': turn['id'], 'result': {'turn': {'id': 'first'}}})
    goal = dict(threadId='fresh', objective=agent_codex.SESSION_GOAL, status='active')
    feed({'method': 'thread/goal/updated', 'params': {'threadId': 'fresh', 'goal': goal}})
    feed({'method': 'item/completed', 'params': {'threadId': 'fresh', 'turnId': 'first',
        'item': {'type': 'agentMessage', 'id': 'prose', 'text': 'Finished this turn.'}}})
    assert not session.done
    feed({'method': 'turn/completed', 'params': {'threadId': 'fresh',
        'turn': {'id': 'first', 'status': 'completed'}}})
    read = take()[0]
    assert read['method'] == 'thread/goal/get'
    feed({'id': read['id'], 'result': {'goal': goal}})
    assert not session.done and not take()

    # A goal continuation is started by the native runtime, never the launcher.
    feed({'method': 'turn/started', 'params': {'threadId': 'fresh', 'turn': {'id': 'automatic'}}})
    feed({'method': 'turn/completed', 'params': {'threadId': 'helper',
        'turn': {'id': 'other', 'status': 'completed'}}})
    complete = dict(goal, status='complete')
    feed({'method': 'thread/goal/updated', 'params': {'threadId': 'fresh', 'goal': complete}})
    assert not session.done
    feed({'method': 'turn/completed', 'params': {'threadId': 'fresh',
        'turn': {'id': 'automatic', 'status': 'completed'}}})
    read = take()[0]
    feed({'id': read['id'], 'result': {'goal': complete}})
    assert session.done and native.status == 0 and not take()
    assert not (tmp_path / 'agent-result.json').exists()

    # Ordinary lifecycle endings supply no test verdict or launcher failure.
    for ended in (None, dict(goal, status='blocked')):
        missing = agent_codex.CodexGoalProtocol(command.request)
        missing.thread = 'fresh'
        list(missing.event({'method': 'turn/completed', 'params': {'threadId': 'fresh',
            'turn': {'id': 'first', 'status': 'completed'}}}))
        list(missing.event({'id': 1, 'result': {'goal': ended}}))
        assert missing.done and missing.status == 0

    failed = agent_codex.CodexGoalProtocol(command.request)
    failed.thread = 'fresh'
    failed.goal = complete
    events = list(failed.event({'method': 'turn/completed', 'params': {'threadId': 'fresh',
        'turn': {'id': 'first', 'status': 'failed',
                 'error': {'message': 'provider failed', 'codexErrorInfo': 'serverOverloaded'}}}}))
    assert failed.done and failed.status == 1
    assert events[0].kind == 'failure' and events[0].data['capacity']

    # Explicit workflow schemas retain their own batch and chat contracts.
    schema = tmp_path / 'response.schema.json'
    schema.write_text('{"type":"object"}')
    structured = command.revised(schema=schema)
    assert '--output-schema' in structured.argv and structured.protocol is None
    assert isinstance(structured.revised(interactive=True).protocol, agent_codex.CodexProtocol)


def test_public_repair_composes_validation_and_continues_pending(tmp_path, monkeypatch):
    import fix_tests
    import test_results

    monkeypatch.setattr(fix_tests, 'repair_inventory', lambda *args: {'system': {'args': ['selected']}})
    monkeypatch.setenv(test_results.VARIABLE, str(tmp_path / 'results' / '1'))
    monkeypatch.setenv(test_results.REPAIR_QUEUE, '1')
    events = []
    def execute(root, run, owner, kind, command=None):
        results = test_results.ResultStore()
        events.append(kind)
        if kind == 'test':
            assert command == [str(root / 'tools/run-tests'), '--stop-on-error', 'system', 'selected',
                               '--vm', 'family-id', '--vmhost', 'test-host']
        if events == ['test']:
            results.record('system', 'test-family', 'passed', 0)
            results.record('system', 'test-family', 'failed', 1, options=['selected'])
            return 1
        if kind == 'agent':
            assert events == ['test', 'agent']  # No pre-repair reproduction.
            prompt = (run / 'prompt.txt').read_text()
            assert '--resume-case=failed' in prompt and 'selected' in prompt
            import test_commands
            assert fix_tests.validation_command(root, command)[0] == 'tools/run-tests'
            assert test_commands.execution_arguments(
                fix_tests.validation_command(root, command)[1:]) == (['system', 'selected'], True)
            assert results.passed('system', 'test-family') == {'passed'}
            results.record('system', 'test-family', 'failed', 0)
            (root / 'concurrent-edit').write_text('ordinary working changes')
            return 0
        assert events == ['test', 'agent', 'test']
        assert results.passed('system', 'test-family') == {'passed', 'failed'}
        return 0

    request = dict(categories=['system'], rounds=1, tasks=None, vm='family-id', vmhost='test-host')
    assert fix_tests.run_rounds(tmp_path, tmp_path, 0, request, operation=execute) == 0
    assert events == ['test', 'agent', 'test']


def _fault_observation_input(monkeypatch, verdict):
    from itertools import count

    from product_failure_observation import FailureObservation
    from tests.support.product_failure_journal import BOOT_ORIGIN

    times = count(10, 10)
    occurred = 25 if verdict == 'allowed' else 15
    events = ([dict(component='broker', category='backend', source='broker', monotonic_usec=occurred)]
              if verdict in ('unexpected', 'allowed') else [])
    complete = verdict != 'blocked'

    def read(self, mode, *args):
        if mode != 'read':
            timestamp = next(times)
            return dict(boot_id='a' * 32, monotonic_usec=timestamp, cursor=str(timestamp),
                        token=BOOT_ORIGIN if mode == 'boot-origin' else f'{timestamp:032x}')
        start, end = map(json.loads, args)
        return dict(span=[start['boot_id'], start['token'], start['monotonic_usec'],
                          end['token'], end['monotonic_usec']],
                    complete=complete, reason='' if complete else 'journal query unavailable',
                    unattributed=0, events=events)

    monkeypatch.setattr(FailureObservation, '_call', read)
    return SimpleNamespace(product_failures=None, lease=object(), config={'domain_id': 1})


def _standalone_observation_command(case, transport, verdict):
    from standalone_product_failures import observe_check, transport_ready

    try:
        with observe_check(case):
            transport_ready(transport)
            if verdict == 'allowed':
                with transport.product_failures.allow('broker', 'backend'):
                    pass
            raise SystemExit(0)
    except SystemExit as error:
        return error.code


def _e2e_observation_command(tmp_path, monkeypatch, case_id, transport):
    import e2e_watch
    import execution
    import suite_lease
    import test_account_password
    from tools import test_retention

    case = dict(case_id=case_id, scenario_id='E2E-022', coverage_id=120,
                title='Reboot with an active grant', preconditions=[], executable={})
    plan = dict(cases=[case], scope='selected', artifacts=str(tmp_path), inventory_sha256='inventory')
    ops = Mock(wraps=os)
    ops.geteuid.return_value = ops.getegid.return_value = 0
    ops.umask.return_value = 0o077
    collector = Mock(path=tmp_path)
    lease = MagicMock(state={'phase': 'complete'},
                      capture=SimpleNamespace(verification_totals={}), online_pending=False)
    lease.__enter__.return_value = lease
    suite = Mock(lease=lease, backend_checked=True)

    def prepare_case(*args, observe_failures, **kwargs):
        observe_failures(transport, 'product-free-start')

    suite.prepare_case.side_effect = prepare_case
    verified = Mock(inputs={'inventory_sha256': 'inventory'})
    verified.contract.return_value = SimpleNamespace(plan={'cases': [case]})
    recorder = Mock(records=[])
    bridge = Mock()

    def acquire(ledger):
        lease.__exit__.side_effect = lambda *error: ledger.pass_outcome('cleanup')
        return None, None, lease

    suite.acquire.side_effect = acquire
    bridge.result.return_value = {'outcome': 'passed'}
    monkeypatch.setattr(execution, 'os', ops)
    monkeypatch.setattr(test_account_password, 'read_password', lambda: 'synthetic-password')
    monkeypatch.setattr(e2e_watch, 'ProgressPublication', Mock())
    monkeypatch.setattr(suite_lease, 'Suite', lambda *args: suite)
    monkeypatch.setattr(test_retention, 'allocate', lambda *args, **kwargs: str(tmp_path))
    monkeypatch.setattr(execution, 'FixtureCredentials', Mock())
    monkeypatch.setattr(execution, 'PrivateCollector', lambda **kwargs: collector)
    monkeypatch.setattr(execution, 'preflight_source', lambda *args, **kwargs: {'source_sha256': 'source'})
    monkeypatch.setattr(execution.system, 'artifact_source', lambda path: path)
    monkeypatch.setattr(execution.system, 'stage_assets', lambda source, path, commands: path.mkdir())
    monkeypatch.setattr(execution.system, 'bootstrap', Mock())
    monkeypatch.setattr(execution, 'VerifiedInputs', lambda **kwargs: verified)
    monkeypatch.setattr(execution, 'ScenarioRecorder', lambda *args, **kwargs: recorder)
    monkeypatch.setattr(execution, 'LeasedScenario', lambda *args, **kwargs: bridge)
    status = execution.main(plan)
    suite.close.assert_called_once_with()
    bridge.execute.assert_called_once()
    return status


def _system_observation_command(tmp_path, monkeypatch, case_id, transport):
    import guest_inputs
    import qualification_storage
    import system_runner
    import system_snapshots
    from system_progress import Progress
    from tools.regression_events import write_event
    from tools import test_retention
    from io import StringIO

    phase, _, case = case_id.partition('::')
    item = system_runner.CaseExecution(phase, 'package', case, False)
    selection = system_runner.Selection('package', case, 'case', (phase,), (), (item,), {})
    ops = Mock(wraps=os)
    ops.geteuid.return_value = ops.getegid.return_value = 0
    ops.umask.return_value = 0o077
    api = Mock()
    api.virEventRunDefaultImpl.side_effect = AssertionError('Started a real VM event loop')
    suite = SimpleNamespace(source=object(), acquire=lambda ledger: (None, None, None))

    def run_attempts(suite, directory, selection, manifest, digest, ledger, **kwargs):
        # Simulate passing case assertions. The controller interval owns the final gate.
        progress = Progress(phase, selection.executions, failures={}, hold=[case])
        guest_output = StringIO()
        write_event(guest_output, 'finished', nodeid='test_install_smoke.py::' + case)
        progress(guest_output.getvalue().encode())
        history = system_runner.HistoryObservation(transport, ledger)
        history.start(item)
        history.close()

        def close():
            ledger.pass_outcome('cleanup')

        suite.close = close
        history.verdict(phase, progress)

    monkeypatch.setattr(system_runner, 'os', ops)
    config = system_runner.baseline.guest_contract.vm_config
    target = SimpleNamespace(require_package_format=lambda: 'deb')
    monkeypatch.setattr(config, 'extract', lambda argv, **kwargs: (argv, target))
    monkeypatch.setattr(config, 'selected', lambda: target)
    monkeypatch.setattr(system_runner, 'resolve_selection', lambda *args, **kwargs: selection)
    monkeypatch.setattr(system_runner, 'shutil', Mock(wraps=system_runner.shutil))
    system_runner.shutil.which.return_value = '/unused'
    monkeypatch.setattr(system_runner, 'importlib', SimpleNamespace(import_module=lambda name: api))
    monkeypatch.setattr(system_runner, 'threading', SimpleNamespace(Thread=Mock()))
    monkeypatch.setattr(system_runner.baseline, 'LibvirtSource', lambda api: suite.source)
    monkeypatch.setattr(qualification_storage, 'session', lambda **kwargs: nullcontext())
    monkeypatch.setattr(test_retention, 'allocate', lambda *args, **kwargs: str(tmp_path))
    monkeypatch.setattr(system_runner, 'artifact_source', lambda path: path)
    (tmp_path / 'input').mkdir()
    monkeypatch.setattr(system_runner, 'stage_assets', lambda *args, **kwargs: {})
    monkeypatch.setattr(system_runner, 'host_fingerprint', lambda commands: {})
    monkeypatch.setattr(system_runner, 'stage_selected_inputs', lambda *args: 'inputs')
    monkeypatch.setattr(guest_inputs, 'Bundle', Mock())
    monkeypatch.setattr(system_snapshots, 'create_suite', lambda *args: suite)
    monkeypatch.setattr(system_snapshots, 'run_attempts', run_attempts)
    monkeypatch.setattr(sys, '__stdout__', sys.stdout)
    return system_runner.main(['--id', '1', '--artifacts', str(tmp_path)])


@pytest.mark.parametrize(('adapter', 'verdict'), [
    ('e2e', 'unexpected'), ('e2e', 'blocked'),
    ('system', 'unexpected'), ('system', 'blocked'),
    ('standalone', 'unexpected'), ('standalone', 'blocked'),
    ('standalone', 'healthy'), ('standalone', 'allowed'),
])
def test_product_observation_routes_only_clear_failure_to_repair(
        tmp_path, monkeypatch, capsys, adapter, verdict):
    import fix_tests
    import regression
    import test_results
    import vm_recording
    import vm_run_times
    import vm_test_queue
    from regression_events import PREFIX
    from regression_process import Control
    from test_checkpoint import Checkpoint
    from io import StringIO
    from threading import Event

    monkeypatch.syspath_prepend(str(ROOT / 'tests/integration'))
    monkeypatch.syspath_prepend(str(ROOT / 'tests/e2e'))
    output_dir = tmp_path / 'adapter'
    output_dir.mkdir(mode=0o700)
    transport = _fault_observation_input(monkeypatch, verdict)
    vm = vm_test_queue.vm_config.load(vm_name(), local=False)
    category = 'e2e' if adapter == 'e2e' else 'system'
    case, options = {
        'e2e': ('E2E-022/reboot-active', ['--id', '120']),
        'system': ('installed::test_installed_package', ['--id', '1']),
        'standalone': ('check_fixture_system_installed', ['check_fixture_system_installed']),
    }[adapter]
    work = dict(category=category, options=options, cases=[case], case=case, area=False)
    selection = [(category, options)]
    plan = ({'concurrency': 1}, [vm], [], [category, *options, '--stop-on-error'],
            selection, {vm.family: [work]})
    monkeypatch.setattr(fix_tests, 'repair_inventory', lambda *args: {category: {'args': options}})
    monkeypatch.setattr(regression.Run, 'wait_for_resources', lambda *args: None)
    monkeypatch.setattr(regression.Run, 'command_environment', lambda *args, **kwargs: {})
    monkeypatch.setattr(vm_run_times, 'Tracker', Mock())
    monkeypatch.delenv(vm_recording.VARIABLE, raising=False)
    monkeypatch.setenv(test_results.VARIABLE, str(tmp_path / 'results' / '1'))
    monkeypatch.setenv(test_results.REPAIR_QUEUE, '1')
    blocked = test_results.OBSERVATION_BLOCKED_STATUS
    failed = verdict == 'unexpected'
    expected_status = 1 if failed else blocked if verdict == 'blocked' else 0
    expected_diagnostic = ('Unexpected product fault broker/backend from broker at guest monotonic 15 us'
                           if failed else 'Product fault observation incomplete (journal query unavailable)')
    attempts, operations = [], []
    commands = []
    outcome = None

    class Ready:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def run_ready(self, execute, *, choose, needed, completed, stop_on_error=True):
            result = dict(status=0, handoffs=[])
            while needed(vm):
                result = completed(vm, execute(SimpleNamespace(vm=vm)))
            return {vm.name: result}

    def command(*args, output, started, **kwargs):
        assert len(attempts) == 1
        started()
        capsys.readouterr()
        with monkeypatch.context() as scoped:
            if adapter == 'standalone':
                status = _standalone_observation_command(case, transport, verdict)
            elif adapter == 'e2e':
                status = _e2e_observation_command(output_dir, scoped, case, transport)
            else:
                status = _system_observation_command(output_dir, scoped, case, transport)
        actual = capsys.readouterr()
        # Replay the command's actual event stream through the ordinary parser.
        output((actual.out + actual.err).encode())
        assert status == expected_status
        if adapter == 'e2e':
            terminal = json.loads(actual.out.splitlines()[-1])
            attempt, = terminal['attempts']
            assert attempt['case_id'] == case and attempt['acceptance_candidate']['outcome'] == 'passed'
            assert terminal['outcome'] == ('failed' if failed else 'observation-blocked')
            context = attempt['product_failure_observation']
        elif adapter == 'system':
            terminal = json.loads((output_dir / 'evidence' / 'result.json').read_text())
            assert terminal['outcome'] == ('failed' if failed else 'observation-blocked')
            assert terminal['observation_blocked_case'] == (None if failed else case)
            context, = terminal['product_observations']
            assert context['phase'] + '::' + context['case_id'] == case
        else:
            context, = [json.loads(line[len(PREFIX):]) for line in actual.out.splitlines()
                        if line.startswith(PREFIX)]
            assert context['nodeid'] == case
            assert context['kind'] == 'product-failure-observation'
            assert context['outcome'] == ('failed' if failed else 'blocked' if status else 'passed')
        assert context['complete'] is (status != blocked)
        assert context['unexpected'] == int(failed)
        assert context['diagnostics'] == ([expected_diagnostic] if status else [])
        return status

    def attempt(worker, assignment, inherited, group):
        assert attempts == [] and assignment['execution']['case'] == case
        attempts.append(case)
        checkpoint = Checkpoint(tmp_path, selection, binding=vm.name)
        checkpoint.state['queue_assignment'] = assignment
        item = regression.Category(category, 1, selection_args=tuple(options))
        report = Mock(directory=tmp_path, dirty=set(), command=commands.append)
        control = Control()
        control.stopped = Event()
        monkeypatch.setattr(control, 'run', command)
        run = regression.Run(tmp_path, report, control, host_only=True)
        run.dashboard.stream = StringIO()
        run.checkpoint = checkpoint
        run.categories = [item]
        argv = [str(tmp_path / 'tools/run-tests'), category, *options]
        status, _ = run.execute(item, argv, events=adapter != 'standalone')
        record, = commands
        assert record['cleanup'] == 'complete'
        assert record['exit_status'] == expected_status
        if adapter != 'standalone':
            assert checkpoint.queue_vm_cleanup is True
        if verdict == 'blocked':
            assert record['state'] == regression.OBSERVATION_BLOCKED
            assert record['failed_ids'] == record['completed_ids'] == []
        return dict(status=run.result_status(), handoffs=[], output_tail=Path(record['log']).read_text(),
                    evidence=dict(assignment, status=status, cleanup=record['cleanup'] == 'complete',
                        passed=sorted(checkpoint.executed_passes.get(category, set())),
                        failed=list(item.failed_nodeids)))

    def operation(root, run, owner, kind, command):
        nonlocal outcome
        operations.append(kind)
        if kind == 'agent':
            assert failed and operations == ['test', 'agent'] and outcome['cleanup_complete'] is True
            assert (command['category'], command['case'], command['vm']) == (category, case, vm.name)
            assert expected_diagnostic in command['output_tail']
            assert fix_tests.validation_command(root, command) == [
                'tools/run-tests', '--stop-on-error', '--resume', '--resume-case=' + case,
                '--resume-case-only', category, *options, '--vm', vm.name]
            return 23  # Stop at the model boundary after observing the request.
        assert operations == ['test']
        assert command == [str(root / 'tools/run-tests'), '--stop-on-error', category,
                           *options, '--vm', vm.name]
        outcome = vm_test_queue.execute_pass(root, plan, SimpleNamespace(stopped=Event()),
                                             attempt)
        assert attempts == [case]
        assert outcome['cleanup_complete'] is True
        assert outcome['status'] == expected_status
        if verdict == 'blocked':
            assert outcome['pending'] is True
        return outcome['status']

    monkeypatch.setattr(vm_test_queue, 'Executor', Ready)
    request = dict(categories=[category], rounds=1, vm=vm.name)
    status = fix_tests.run_rounds(tmp_path, tmp_path, 0, request, operation=operation)
    assert status == (23 if failed else expected_status)
    assert operations == (['test', 'agent'] if failed else ['test'])
    results = test_results.ResultStore()
    assert results.passed(category, vm.family) == (set() if expected_status else {case})
    if not failed:
        assert not results.failures() and results.failure() is None


def test_public_repair_resume_keeps_clear_results_and_ignores_partial_state(tmp_path, monkeypatch):
    import fix_tests
    import regression_session
    import test_results
    import vm_selection
    from io import StringIO

    monkeypatch.delenv(regression_session.FRAME_DIRECTORY, raising=False)
    incomplete = tmp_path / 'interrupted-run'
    incomplete.mkdir(mode=0o700)
    # Diagnostic output is optional; only a readable final verdict counts.
    assert regression_session.follow(incomplete, StringIO()) == test_results.PENDING_STATUS
    (incomplete / 'result').write_text('{')
    assert regression_session.follow(incomplete, StringIO()) == test_results.PENDING_STATUS
    (incomplete / 'result').write_text('0')
    assert regression_session.follow(incomplete, StringIO()) == 0

    # A repair invocation waits for unrelated work, then starts its own selected
    # run. Neither the foreign verdict nor old startup metadata grants a pass.
    (tmp_path / 'current.json').write_text('{"run":')
    assert regression_session.current_session(tmp_path) == (None, False)
    selected = tmp_path / 'selected-run'
    selected.mkdir()
    choices = iter(((incomplete, False), (selected, True)))
    with monkeypatch.context() as scoped:
        scoped.setenv(test_results.VARIABLE, str(tmp_path / 'results' / '1'))
        scoped.setenv('ONPC_RUNNER_INVOCATION', '1')
        scoped.setattr(regression_session, 'select', lambda *args, **kwargs: next(choices))
        followed = []
        scoped.setattr(regression_session, 'follow', lambda run: followed.append(run) or 1)
        assert regression_session.main(tmp_path, ['unit', 'selected']) == 1
        assert followed == [selected]

    monkeypatch.setattr(fix_tests, 'repair_inventory', lambda *args: {'unit': {'args': []}})
    monkeypatch.setattr(vm_selection, 'execution_binding', lambda: None)
    monkeypatch.setenv(test_results.VARIABLE, str(tmp_path / 'results' / '1'))
    monkeypatch.setenv(test_results.REPAIR_QUEUE, '1')
    results = test_results.ResultStore()
    results.record('unit', 'host', 'passed', 0)
    results.record('unit', 'host', 'failed', 1)
    (results.path / 'partial.json').write_text('{"case":')
    (tmp_path / 'progress.json').write_text('{"completed_categories":[{}]}')
    (tmp_path / 'checkpoint.json').write_text('{"pending":"abandoned transaction"}')
    (tmp_path / 'agent-thread.json').write_text('{"turns":"incomplete"}')
    events = []
    def execute(root, run, owner, kind, command=None):
        events.append(kind)
        if kind == 'agent':
            assert events.count('agent') <= 2
            assert results.passed('unit', 'host') == {'passed'}
            if events.count('agent') == 2:
                results.record('unit', 'host', 'failed', 0)
        elif results.select_failure('unit', 'host', ['passed', 'failed'], []):
            return 1  # Discovery chooses the failure without running its body.
        elif events.count('test') == 3:
            from vm_test_queue import PENDING_STATUS
            # An incomplete invocation is pending, not a new repair session.
            assert not results.failures()
            return PENDING_STATUS
        return 0
    request = dict(categories=['unit'], rounds=1, tasks=None)
    assert fix_tests.run_rounds(tmp_path, tmp_path, 0, request, operation=execute) == 0
    assert events == ['test', 'agent', 'test', 'agent', 'test', 'test']
    assert results.passed('unit', 'host') == {'passed', 'failed'}


def test_logical_task_admission_survives_resume_and_limit_changes(tmp_path, monkeypatch):
    from launcher_runtime import TaskBudget

    budget = TaskBudget(tmp_path)
    budget.initialize(3)
    assert budget.admit(key='round-1:system', concurrent=True)
    assert budget.admit(key='round-1:e2e', concurrent=True)
    resumed = TaskBudget(tmp_path)
    resumed.set_limit(1)
    assert resumed.admit(key='round-1:system', concurrent=True)
    assert resumed.complete(key='round-1:system')
    assert not budget.complete(key='round-1:system')
    assert budget.complete(key='round-1:e2e')
    assert not budget.admit(key='round-2:all', concurrent=True)
    assert budget.read()['started'] == budget.read()['completed'] == 2

    import fix_tests
    monkeypatch.setattr(fix_tests, 'previous_request', lambda *args: dict(
        categories=['unit'], vm=None, rounds=2, model=None, effort=None, tasks=1))
    admitted = []
    monkeypatch.setattr(fix_tests, 'select', lambda root, request, **options:
                        admitted.append((request, options)) or (tmp_path, True))
    monkeypatch.setattr(fix_tests.launcher, 'report_start', lambda *args, **kwargs: 0)
    assert fix_tests.main(['--resume', '--tasks', '2']) == 0
    request, options = admitted[0]
    assert request['tasks'] == 2 and request['rounds'] == 2
    assert request['categories'] == ['unit'] and options['resume']
    import vm_selection
    monkeypatch.setattr(vm_selection, 'execution_binding', lambda: None)
    from test_progress import SELECTION, repair_selection
    from test_results import REPAIR_QUEUE
    monkeypatch.setenv(REPAIR_QUEUE, '1')
    monkeypatch.delenv(SELECTION, raising=False)
    monkeypatch.setattr(fix_tests, 'repair_inventory', lambda *args: {'unit': {'args': []},
                                                                    'component': {'args': []}})
    calls = []
    request = dict(categories=['unit', 'component'], rounds=2, tasks=1)
    def execute(root, run, owner, kind, command):
        calls.append((kind, command[2:], repair_selection()))
        return 0
    assert fix_tests.run_rounds(tmp_path, tmp_path, 0, request, operation=execute) == 0
    # Re-entering the same invocation models worker replacement by --reload.
    assert fix_tests.run_rounds(tmp_path, tmp_path, 0, request, operation=execute) == 0
    assert calls == [('test', ['unit'], ['unit', 'component'])]
    assert SELECTION not in os.environ


def test_requested_rounds_repeat_same_repair_workflow_and_resume(tmp_path, monkeypatch):
    import fix_tests
    import test_results
    import vm_selection
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    monkeypatch.setattr(fix_tests, 'repair_inventory', lambda *args: {'unit': {'args': []}})
    monkeypatch.setattr(vm_selection, 'execution_binding', lambda: None)
    monkeypatch.setenv(test_results.VARIABLE, '')
    monkeypatch.setenv(test_results.REPAIR_QUEUE, '1')
    original = tmp_path / 'original'
    original.mkdir(mode=0o700)
    request = dict(categories=['unit'], rounds=3, tasks=None)
    (original / 'request.json').write_text(json.dumps(request))
    calls = []
    def execute(root, run, owner, kind, command=None):
        results = test_results.ResultStore()
        calls.append((results.directory.name, kind))
        if kind == 'agent':
            assert command['case'] == 'failed'
            assert results.passed('unit', 'host') == {'passed'}
            results.record('unit', 'host', 'failed', 0)
            return 0
        assert command == [str(root / 'tools/run-tests'), '--stop-on-error', 'unit']
        (root / 'concurrent-edit').write_text(str(len(calls)))
        if not results.passed('unit', 'host'):
            results.record('unit', 'host', 'passed', 0)
            results.record('unit', 'host', 'failed', 1)
            if results.directory.name == '2':
                return 130  # Interrupt after round 2 has checkpointed work.
            return 1
        if results.select_failure('unit', 'host', ['passed', 'failed'], []):
            assert results.directory.name == '2'
            return 1  # Resume discovers the saved failure without reproducing it.
        assert results.passed('unit', 'host') == {'passed', 'failed'}
        return 0
    with pytest.raises(fix_tests.launcher.Stopped):
        fix_tests.run_rounds(tmp_path, original, 0, request, operation=execute)
    expected = [('1', 'test'), ('1', 'agent'), ('1', 'test'), ('2', 'test')]
    assert calls == expected

    # Exercise bare --resume, including request restoration and copying the
    # per-round results into the newly allocated launcher run.
    resumed = tmp_path / 'resumed'
    monkeypatch.setattr(fix_tests, 'previous_run',
                        lambda root, kind: original if kind == 'fix-tests-host' else None)
    def start(root, kind, command, *, on_start, **kwargs):
        assert kind == 'fix-tests-host'
        command(resumed, 0)
        resumed.mkdir(mode=0o700)
        on_start(resumed)
        return resumed, True
    monkeypatch.setattr(fix_tests.launcher, 'select', start)
    monkeypatch.setattr(fix_tests.launcher, 'report_start', lambda *args, **kwargs: 0)
    assert fix_tests.main(['--resume']) == 0
    restored = fix_tests.read_json(resumed / 'request.json')
    assert restored['rounds'] == 3 and restored['categories'] == ['unit']
    assert test_results.ResultStore(resumed / 'results' / '2').passed('unit', 'host') == {'passed'}
    assert fix_tests.run_rounds(tmp_path, resumed, 0, restored, operation=execute) == 0
    expected += [(number, kind) for number in ('2', '3') for kind in ('test', 'agent', 'test')]
    assert calls == expected
    assert fix_tests.run_rounds(tmp_path, resumed, 0, restored, operation=execute) == 0
    assert calls == expected


def test_baseline_queue_drains_and_cancels_pending_work_before_refresh(tmp_path, monkeypatch, capsys):
    from contextlib import contextmanager
    from dataclasses import replace
    import threading
    import host_dispatch
    import regression_process
    import test_retention
    import test_source
    import test_storage
    import vm_pool
    from preparation_report import PREFIX
    from vm_queue import prepare_hosts
    import host_compute
    monkeypatch.setattr(host_compute, 'launch',
                        lambda vms: pytest.fail('preparation must queue the full selection'))
    from vm_selection import vm_config

    names = [f'vm-{index}' for index in range(33)]
    vms = tuple(vm_config.VMConfig(name, tmp_path / name, enabled=True) for name in names)
    configured = {vm.name: vm for vm in vms}
    monkeypatch.setattr(vm_config, 'load', configured.__getitem__)
    monkeypatch.setattr(vm_config, 'execution', lambda _, **kwargs: (len(vms), vms))
    monkeypatch.setattr(test_source, 'startup', lambda *a, **k: nullcontext())
    monkeypatch.setattr(test_source, 'reader', lambda *a, **k: nullcontext())
    monkeypatch.setattr(test_source, 'finish_admission', lambda: None)
    monkeypatch.setattr(test_storage, 'storage_root', lambda root=None: tmp_path)
    launcher = runpy.run_path(str(ROOT / 'tools/prepare-vm'))
    main = launcher['main']
    monkeypatch.setitem(main.__globals__, 'read_password', lambda: None)
    monkeypatch.setitem(main.__globals__, 'check', lambda _: None)
    monkeypatch.setitem(main.__globals__, 'tool_host', lambda _: vms[0].host)
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    held, calls, refreshes = set(), [], []
    stopped = threading.Event()
    inherited = test_retention.environment()
    cancel_after_two = False

    @contextmanager
    def reservation(name, *, stopped, bind, wait, stderr):
        assert not bind
        assert not wait
        held.add(name)
        try:
            yield name + '-receipt'
        finally:
            held.remove(name)

    @contextmanager
    def installed(control, **kwargs):
        control.stopped = stopped
        yield control

    def execute(control, command, *, env, **kwargs):
        assert test_retention.environment() == inherited
        assert all(env.get(name) == inherited.get(name)
                   for name in (test_retention.VARIABLE, test_retention.OWNER_VARIABLE))
        if command[0] == str(ROOT / 'setup.sh'):
            assert not held, 'helper refresh ran before VM checkin'
            assert command == [str(ROOT / 'setup.sh'), '--test-tools-only']
            assert not control.stopped.is_set() and kwargs['wait_on_cancel']
            refreshes.append(command)
            details = f'Helper refresh {len(refreshes)} details\n'.encode()
            kwargs['output'](details)
            allocations = test_storage.directory('allocations', root=ROOT)
            assert any(details in log.read_bytes() for log in allocations.glob('*/hosts/*.log'))
            return 0
        name = env[vm_config.VARIABLE]
        assert name in held
        assert env[vm_pool.VARIABLE] == name + '-receipt'
        assert control.stopped is not stopped  # Baseline has no stop protocol.
        assert kwargs['wait_on_cancel']  # A report failure must also wait for replacement.
        kwargs['output'](b'Worker output\n')
        calls.append(name)
        if len(calls) == 1:
            return 1  # Failure must not prevent the next preparation.
        if cancel_after_two:
            stopped.set()
        assert not control.stopped.is_set()
        return 0  # Active replacement finishes despite outer cancellation.

    monkeypatch.setattr(vm_pool, 'reservation', reservation)
    monkeypatch.setattr(regression_process.Control, 'installed', installed)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    options = ['--mode', 'auto', '--vm', ','.join(names), '--y']
    assert main(options) == 1
    assert len(calls) == len(names) and set(calls) == set(names)
    assert len(refreshes) == 1 and not held

    calls.clear()
    cancel_after_two = True
    open_log = Path.open

    def fail_worker_logs(path, mode='r', *args, **kwargs):
        if mode == 'ab' and path.parent.name.startswith('onpc-prep-'):
            raise OSError('worker log storage unavailable')
        return open_log(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', fail_worker_logs)
        assert main(options) == 130
    assert len(calls) == 2 and len(refreshes) == 2
    assert not held
    assert 'Preparation report incomplete: worker log storage unavailable' in capsys.readouterr().err

    # One transfer carries a complete remote queue while local work can proceed.
    stopped.clear()
    remote_host = replace(vms[0].host, name='remote')
    remote_vms = tuple(replace(vm, host=remote_host) for vm in vms[:-1])
    remote_started, local_finished = threading.Event(), threading.Event()
    remote_dispatches = []

    def remote(root, vm, tool, options, *, control, output, stderr_output):
        assert tool == 'prepare-appsnapshot' and vm == remote_vms[0]
        assert options == ['--vm', ','.join(names[:-1]), '--y', '--overwrite', 'false',
                           '--queue-host', 'remote']
        remote_dispatches.append(vm.host.name)
        remote_started.set()
        assert local_finished.wait(5), 'remote queue blocked another host'
        for target in remote_vms:
            output(PREFIX + json.dumps([target.name, 'state', 0]).encode() + b'\n')
        return 255  # The connection dropped before confirming the host's result.

    def local(options, control, targets, report):
        assert targets == [vms[-1]]
        assert remote_started.wait(5)
        local_finished.set()
        return 0

    monkeypatch.setattr(test_source, 'leave_checkout', lambda: None)
    monkeypatch.setattr(host_dispatch, 'vm_tool', remote)
    assert prepare_hosts(ROOT, 'prepare-appsnapshot', ['--overwrite', 'false'],
                         (*remote_vms, vms[-1]), vms[-1].host.name, local) == 255
    assert remote_dispatches == ['remote']
    recap = capsys.readouterr().out
    assert f'✓ [{remote_vms[0].name}] App snapshot ready' in recap
    assert f'✗ [{remote_vms[-1].name}] Preparation failed' in recap

    with monkeypatch.context() as patch:
        patch.setattr(vm_config, 'execution', lambda _, **kwargs: (len(vms) - 1, vms[:-1]))
        assert main([*options, '--queue-host', vms[0].host.name]) == 2
    assert len(calls) == 2, 'a partially transferred selection started preparation'

    # Reusing a snapshot in the rolling queue must release an owned running VM.
    import prepare_appsnapshot as app
    actions = []

    def probe(control, command, **kwargs):
        assert '--probe' in command
        actions.append('probe')
        return 4

    with monkeypatch.context() as patch:
        patch.setattr(os, 'environ', os.environ.copy())
        patch.setattr(host_dispatch, 'tool_host', lambda root: vms[0].host)
        patch.setattr(vm_config, 'execution', lambda _: (1, vms[:1]))
        patch.setattr(app, 'arguments', lambda _: SimpleNamespace(vm=names[0], queue_host=None,
                      overwrite='false', release_notes_upgrade=False))
        patch.setattr(app, 'select', lambda name: None)
        patch.setattr(app, 'vm_arguments', lambda: ['--vm', names[0]])
        patch.setattr(app, 'check', lambda helper: None)
        patch.setattr(app, 'snap_ready_reservation', lambda *args: nullcontext())
        patch.setattr(app.test_activity, 'activity', lambda *args, **kwargs: nullcontext())
        patch.setattr(app.test_launcher, 'environment', lambda root: {})
        patch.setattr(app, 'cleanup', lambda root: actions.append('cleanup') or 0)
        patch.setattr(regression_process.Control, 'run', probe)
        assert app.main(_worker=True, _snapshot_only=True) == 0
    assert actions == ['probe', 'cleanup']


@pytest.fixture
def shared_closeout(tmp_path, monkeypatch):
    import detached_launcher as launcher
    import launcher_git
    import plan_launcher
    import test_storage

    root = tmp_path / 'checkout'
    root.mkdir()
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
               GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')

    def git(*args):
        return subprocess.run(['git', *args], cwd=root, env=env, check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()

    git('init', '--initial-branch=main')
    shared = root / 'shared.py'
    shared.write_text('committed\n')
    skill = root / '.agents/skills/commit/SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('Controlled test: no commit helper may execute.\n')
    git('add', 'shared.py')
    git('add', '.agents/skills/commit/SKILL.md')
    git('commit', '-m', 'Private fixture')
    git('config', 'branch.main.remote', '.')
    git('config', 'branch.main.merge', 'refs/heads/main')
    shared.write_text('unrelated original work\n')
    baseline = launcher_git.worktree_snapshot(root)
    shared.write_text('unrelated original work\ntask change\n')
    spec = plan_launcher.PlanWorkflow('execute-plan', plan='master.md')
    directory = launcher.private_directory(tmp_path / 'plans' / plan_launcher.plan_namespace(spec.plan))
    run = launcher.private_directory(directory / ('a' * 32))
    launcher.atomic(directory / 'current.json', {'run': run.name})
    result = dict(status='task_complete', task_id='001', summary='Accepted', handoff='Close out',
                  cleanup_complete=True, stage_paths=['shared.py'], blocker=None,
                  checks=[dict(kind='host', target='', result='passed')])
    state = dict(task_id='001', task=dict(task_id='001', acceptance='host', targets=[],
                                         brief=str(root / 'removed-brief.md')),
                 plan_queue='queue.md', stage_baseline=baseline, protected_staged=[],
                 git_reconciliation=dict(ownership_paths=['shared.py'], accepted_result=result))
    launcher.atomic(run / 'checkpoint.json', state)
    monkeypatch.setattr(test_storage, 'directory', lambda *args, **kwargs: tmp_path / 'plans')
    with launcher.lock(directory / 'owner') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        yield root, run, spec, state, git, owner


def test_shared_closeout_review_preserves_original_work(shared_closeout, monkeypatch):
    import launcher_git
    import plan_launcher

    root, run, spec, state, git, _owner = shared_closeout
    checkpoint = (run / 'checkpoint.json').read_bytes()
    working = (root / 'shared.py').read_bytes()
    index = git('ls-files', '--stage')
    head = git('rev-parse', 'HEAD')
    original = json.loads(json.dumps(state))
    with pytest.raises(launcher_git.OwnershipReconciliationRequired):
        launcher_git.validate_closeout_ownership(root, ['shared.py'], state, run=run)
    preview = plan_launcher.review_ownership(root, spec, run.name, check=True)
    assert not (run / 'ownership-review.json').exists()
    with pytest.raises(ValueError, match='inputs changed'):
        plan_launcher.review_ownership(root, spec, run.name, approval='wrong')
    plan_launcher.review_ownership(root, spec, run.name, approval=preview['approval'])
    launcher_git.validate_closeout_ownership(root, ['shared.py'], state, run=run)
    assert state == original  # Approval never retires the protected fingerprints.
    assert (run / 'reload.json').exists()
    assert (run / 'checkpoint.json').read_bytes() == checkpoint
    assert (root / 'shared.py').read_bytes() == working
    assert git('ls-files', '--stage') == index and git('rev-parse', 'HEAD') == head

    # Exercise the actual close-out path through the former refusal. Stop at
    # the controller's supervised commit boundary; this test never commits work.
    state.update(in_flight=False, repair_sessions=3, task_sessions=4)
    plan = SimpleNamespace(root=root, path='master.md', queue='queue.md',
                           state=lambda **kwargs: {'001': False})
    plan_launcher.recover_reviewed_completion(plan, run, state)
    assert 'pending_completion' not in state  # An unfinished row stays unfinished.
    plan.state = lambda **kwargs: {'001': True}
    plan_launcher.recover_reviewed_completion(plan, run, state)
    assert state['pending_completion'] == state['git_reconciliation']['accepted_result']
    assert (state['repair_sessions'], state['task_sessions']) == (3, 4)
    monkeypatch.setattr(plan_launcher.launcher, 'finish_nested', lambda *args: None)
    pull = Mock()
    commit = Mock()
    monkeypatch.setattr(plan_launcher, 'pull_before_commit', pull)
    monkeypatch.setattr(plan_launcher, 'commit_push_propagate', commit)
    assert plan_launcher._closeout(plan, spec, run, state)
    pull.assert_called_once()
    commit.assert_called_once()
    assert state['stage_baseline'] == original['stage_baseline']
    assert (root / 'shared.py').read_bytes() == working
    assert git('ls-files', '--stage') == index and git('rev-parse', 'HEAD') == head


@pytest.mark.parametrize('change', ['working', 'index', 'task'])
def test_shared_closeout_review_refuses_changed_inputs(shared_closeout, change):
    import launcher_git
    import launcher_worktrees
    import plan_launcher

    root, run, spec, state, git, _owner = shared_closeout
    preview = plan_launcher.review_ownership(root, spec, run.name, check=True)
    plan_launcher.review_ownership(root, spec, run.name, approval=preview['approval'])
    identity, head = launcher_git.validate_pull_identity(root, state)
    state['commit_intent'] = dict(engine='skill', session='b' * 32, parent=head,
        paths=['shared.py'], message='Fixture closeout', targets=[], **identity,
        ownership_review=json.loads((run / 'ownership-review.json').read_text()))
    if change == 'working':
        (root / 'shared.py').write_text('new work from another owner\n')
    elif change == 'index':
        git('add', 'shared.py')
    else:
        state['task']['task_id'] = state['task_id'] = '002'
    before = json.loads(json.dumps(state))
    with pytest.raises(launcher_git.OwnershipReconciliationRequired):
        launcher_git.validate_closeout_ownership(root, ['shared.py'], state, run=run)
    assert state == before
    # A crash after intent persistence must not bypass the same freshness guard.
    from unittest.mock import patch
    with patch.object(launcher_worktrees, 'commit_skill_targets', return_value=[]), \
            pytest.raises(launcher_git.OwnershipReconciliationRequired):
        launcher_git._commit_with_skill(root, run, state, ['shared.py'], 'Fixture closeout',
                                       git=launcher_git.git_output)
    assert state == before


def test_shared_closeout_review_retires_only_resolved_overlaps(shared_closeout):
    import detached_launcher as launcher
    import launcher_git
    import plan_launcher

    root, run, spec, state, git, _owner = shared_closeout
    second = root / 'second.py'
    second.write_text('committed second\n')
    git('add', 'second.py')
    git('commit', '-m', 'Second private fixture')
    second.write_text('unrelated second\n')
    original = launcher_git.worktree_fingerprint(second)
    state['stage_baseline']['second.py'] = original
    state['git_reconciliation']['ownership_paths'].append('second.py')
    second.write_text('unrelated second\ntask change\n')
    launcher.atomic(run / 'checkpoint.json', state)
    preview = plan_launcher.review_ownership(root, spec, run.name, check=True)
    plan_launcher.review_ownership(root, spec, run.name, approval=preview['approval'])
    (root / 'shared.py').write_text('committed\n')
    launcher_git.validate_closeout_ownership(root, ['shared.py', 'second.py'], state, run=run)
    assert state['stage_baseline'] == {'second.py': original}
    second.write_text('committed second\n')
    launcher_git.validate_closeout_ownership(root, ['shared.py', 'second.py'], state, run=run)
    assert not state['stage_baseline']
    assert launcher_git.approved_ownership_review(root, run, state) is None


def test_shared_closeout_review_keeps_journaled_commit_recovery(shared_closeout, monkeypatch):
    import detached_launcher as launcher
    import launcher_git
    import launcher_worktrees
    import plan_launcher

    root, run, spec, state, git, _owner = shared_closeout
    preview = plan_launcher.review_ownership(root, spec, run.name, check=True)
    plan_launcher.review_ownership(root, spec, run.name, approval=preview['approval'])
    identity, parent = launcher_git.validate_pull_identity(root, state)
    state['commit_intent'] = dict(engine='skill', session='b' * 32, parent=parent,
        paths=['shared.py'], message='Fixture closeout', targets=[], **identity,
        ownership_review=json.loads((run / 'ownership-review.json').read_text()))
    git('add', 'shared.py')
    git('commit', '-m', 'Journaled private commit')
    commit = git('rev-parse', 'HEAD')
    sessions = launcher.private_directory(run / 'commit-skill')
    session = launcher.private_directory(sessions / ('b' * 32))
    launcher.atomic(session / 'progress.json', dict(source_commit=commit, pushed_head=commit))
    launcher.atomic(session / 'agent-result.json', dict(status='complete'))
    monkeypatch.setattr(launcher_worktrees, 'commit_skill_targets', lambda *args, **kwargs: [])
    assert launcher_git._commit_with_skill(root, run, state, ['shared.py'], 'Fixture closeout',
                                          git=launcher_git.git_output) == commit


def test_shared_closeout_reapproval_recovers_rejected_uncommitted_intent(shared_closeout, monkeypatch):
    import launcher_git
    import launcher_worktrees
    import plan_launcher

    root, run, spec, state, git, _owner = shared_closeout
    preview = plan_launcher.review_ownership(root, spec, run.name, check=True)
    plan_launcher.review_ownership(root, spec, run.name, approval=preview['approval'])
    identity, parent = launcher_git.validate_pull_identity(root, state)
    state['commit_intent'] = dict(engine='skill', session='b' * 32, parent=parent,
        paths=['shared.py'], message='Fixture closeout', targets=[], **identity,
        ownership_review=json.loads((run / 'ownership-review.json').read_text()))
    state.update(pending_completion=state['git_reconciliation']['accepted_result'],
                 in_flight=False, repair_sessions=3, task_sessions=4)
    (root / 'shared.py').write_text('unrelated original work\nrevalidated task revision\n')
    plan = SimpleNamespace(root=root, path='master.md', queue='queue.md',
                           state=lambda **kwargs: {'001': True})
    monkeypatch.setattr(plan_launcher.launcher, 'finish_nested', lambda *args: None)
    monkeypatch.setattr(plan_launcher, 'pull_before_commit', Mock())
    monkeypatch.setattr(launcher_worktrees, 'commit_skill_targets', lambda *args, **kwargs: [])
    monkeypatch.setattr(plan_launcher, 'commit_push_propagate', lambda *args, **kwargs:
        launcher_git._commit_with_skill(root, run, state, ['shared.py'], 'Fixture closeout',
                                        git=launcher_git.git_output))
    assert not plan_launcher.closeout(plan, spec, run, state)
    assert 'pending_completion' not in state and state['commit_intent']['parent'] == parent
    preview = plan_launcher.review_ownership(root, spec, run.name, check=True)
    plan_launcher.review_ownership(root, spec, run.name, approval=preview['approval'])
    plan_launcher.recover_reviewed_completion(plan, run, state)
    assert state['pending_completion']['task_id'] == '001'
    assert (state['repair_sessions'], state['task_sessions']) == (3, 4)
    commit = Mock()
    monkeypatch.setattr(plan_launcher, 'commit_push_propagate', commit)
    assert plan_launcher.closeout(plan, spec, run, state)
    commit.assert_called_once()
    assert state['stage_baseline']['shared.py']
    assert git('rev-parse', 'HEAD') == parent
    assert not git('diff', '--cached', '--name-only')


def test_shared_closeout_review_refuses_inactive_controller(shared_closeout):
    import plan_launcher

    root, run, spec, state, git, owner = shared_closeout
    checkpoint = (run / 'checkpoint.json').read_bytes()
    fcntl.flock(owner, fcntl.LOCK_UN)
    with pytest.raises(ValueError, match='active controller; start the same plan'):
        plan_launcher.review_ownership(root, spec, run.name, check=True)
    assert not (run / 'ownership-review.json').exists()
    assert not (run / 'reload.json').exists()
    assert (run / 'checkpoint.json').read_bytes() == checkpoint


def test_checkout_source_exclusive_sync_waits_for_live_readers(tmp_path, isolated_source):
    import detached_launcher as launcher
    import test_source
    from launcher_controller import synchronize_boundary, synchronize_reload, upstream_update_ready
    from launcher_source_sync import SyncError
    from regression_process import Control
    from test_storage import directory

    root = tmp_path / 'checkout'
    root.mkdir()

    def git(*args):
        return subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *args],
                              cwd=root, check=True, capture_output=True, text=True, timeout=10).stdout.strip()

    git('init', '--initial-branch=main')
    git('commit', '--allow-empty', '-m', 'Base')
    base = git('rev-parse', 'HEAD')
    git('switch', '-c', 'published')
    git('commit', '--allow-empty', '-m', 'Upstream advance')
    upstream = git('rev-parse', 'HEAD')
    git('switch', 'main')
    git('config', 'branch.main.remote', '.')
    git('config', 'branch.main.merge', 'refs/heads/published')

    sessions = directory('sessions', root=root)
    run = launcher.private_directory(sessions / ('a' * 32))
    launcher.atomic(sessions / 'current.json', {'run': run.name})
    host_sessions = directory('sessions-host', root=root)
    host_run = launcher.private_directory(host_sessions / ('b' * 32))
    launcher.atomic(host_sessions / 'current.json', {'run': host_run.name})
    with (launcher.lock(run / 'owner') as owner, launcher.lock(host_run / 'owner') as host_owner,
          launcher.lock(tmp_path / 'source.lock') as reader):
        fcntl.flock(owner, fcntl.LOCK_EX)
        fcntl.flock(host_owner, fcntl.LOCK_EX)
        control = Control()
        assert not upstream_update_ready(root, 'main', run, control=control)
        assert not synchronize_boundary(root, 'main', run)
        fcntl.flock(host_owner, fcntl.LOCK_UN)

        with launcher.lock(root / '.git/onpc-worktree-propagation.lock') as transaction:
            fcntl.flock(transaction, fcntl.LOCK_EX)
            assert not upstream_update_ready(root, 'main', run, control=control)

        assert isolated_source.admit(reader)
        isolated_source.validate(reader, held=True)
        assert not upstream_update_ready(root, 'main', run, control=control)
        fcntl.flock(reader, fcntl.LOCK_UN)
        assert upstream_update_ready(root, 'main', run, control=control)

        # Ownership can change after the probe while the runner joins its work.
        assert isolated_source.admit(reader)
        assert not synchronize_boundary(root, 'main', run)
        with pytest.raises(SyncError, match='checkout synchronization is busy'):
            synchronize_reload(root, run)
        assert git('rev-parse', 'HEAD') == base
        fcntl.flock(reader, fcntl.LOCK_UN)
        assert synchronize_boundary(root, 'main', run)
        assert git('rev-parse', 'HEAD') == upstream

        fcntl.flock(reader, fcntl.LOCK_EX)
        control.stop()
        with pytest.raises(launcher.Stopped), test_source.admission(
                root, [], stopped=control.stopped.is_set):
            pytest.fail('cancelled startup acquired a source reader')


@pytest.fixture
def isolated_source(tmp_path, monkeypatch):
    import threading
    import test_source

    # This checkout owns only its private leases, never the outer test runner's.
    for name in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS,
                 test_source.STARTUP_READER, test_source.STARTUP_WRITER):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(test_source, '_local', threading.local())
    monkeypatch.setattr(test_source, 'source_directory', lambda root, **options: tmp_path)
    return test_source.SourceProtection(tmp_path)


def test_checkout_source_forwards_only_the_calling_workers_lease(tmp_path, isolated_source):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import test_source
    import detached_launcher
    from test_storage import scratch_descriptors
    from watch_recording_worker import shared_owner_descriptors

    overlap = threading.Barrier(2, timeout=5)
    def admitted():
        with test_source.reader(tmp_path) as descriptor:
            overlap.wait()
            assert test_source.descriptors() == (descriptor,)
            assert test_source.environment() == {test_source.VARIABLE: str(descriptor)}
            command_env = detached_launcher.agent_environment(dict(
                test_source.environment(), ONPC_TEST_SOURCE_WRITER='repair-owner',
                ONPC_TEST_SOURCE_IMPORT_FD=str(descriptor), ONPC_REPAIR_STARTUP_FD=str(descriptor),
                ONPC_REPAIR_WRITER_FD=str(descriptor), PATH='/native/bin'))
            # Native execution may close all inherited FDs. No source authority
            # label survives, while the real caller still owns its held lease.
            assert command_env == {'PATH': '/native/bin'}
            isolated_source.validate(descriptor, held=True)
            assert set(shared_owner_descriptors()) == set(scratch_descriptors()) - {descriptor}
            overlap.wait()
            return descriptor
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(admitted) for _ in range(2)]
        descriptors = [future.result(timeout=10) for future in futures]
    assert len(set(descriptors)) == 2
    assert test_source.descriptors() == ()


def test_checkout_source_startup_release_clears_only_owned_aliases(
        tmp_path, monkeypatch, isolated_source):
    import detached_launcher as launcher
    import test_source

    with launcher.lock(tmp_path / 'source.lock') as descriptor:
        assert isolated_source.admit(descriptor)
        startup = os.dup(descriptor)
        monkeypatch.setenv(test_source.VARIABLE, str(startup))
        monkeypatch.setenv(test_source.STARTUP_READER, str(startup))
        monkeypatch.setenv(test_source.IMPORTS, str(startup))
        test_source.finish_imports(tmp_path)
        assert test_source.environment() == {} and test_source.descriptors() == ()
        assert test_source.STARTUP_READER not in os.environ and test_source.IMPORTS not in os.environ
        with pytest.raises(OSError):
            os.fstat(startup)
        isolated_source.validate(descriptor, held=True)


def test_checkout_source_privileged_borrow_keeps_the_actual_lease_in_descendants(
        tmp_path, isolated_source):
    import detached_launcher as launcher
    import test_source
    from test_storage import scratch_descriptors

    holder = '''import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from test_source import SourceProtection, _lock
source = SourceProtection(Path(sys.argv[2]))
with _lock(source.directory / 'source.lock') as descriptor:
    assert source.admit(descriptor)
    print('ready', flush=True)
    sys.stdin.read()
'''
    descendant = '''import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from test_source import SourceProtection, VARIABLE, WRITER
source = SourceProtection(Path(sys.argv[2]))
source.validate(int(os.environ[VARIABLE]), held=True, writer=WRITER in os.environ)
print('ready', flush=True)
sys.stdin.read()
'''
    for owner in (None,):
        with subprocess.Popen([sys.executable, '-B', '-c', holder, str(ROOT / 'tools'),
                               str(tmp_path), owner or ''], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True) as caller:
            child = None
            try:
                from selectors import DefaultSelector, EVENT_READ
                with DefaultSelector() as ready:
                    ready.register(caller.stdout, EVENT_READ)
                    assert ready.select(5), 'source holder did not start'
                    assert caller.stdout.readline().strip() == 'ready'
                with pytest.raises(ValueError, match='authenticated caller'):
                    with test_source._borrow_process(tmp_path, os.geteuid() + 1, caller.pid):
                        pytest.fail('a different UID cannot lend source authority')
                with test_source._borrow_process(tmp_path, os.geteuid(), caller.pid):
                    descriptor, = test_source.descriptors()
                    isolated_source.validate(descriptor, held=True, writer=owner is not None)
                    caller.communicate(timeout=5)  # Original owner has exited.
                    assert caller.returncode == 0
                    child = subprocess.Popen(
                        [sys.executable, '-B', '-c', descendant, str(ROOT / 'tools'), str(tmp_path)],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                        env={**os.environ, **test_source.environment()}, pass_fds=scratch_descriptors())
                    with DefaultSelector() as ready:
                        ready.register(child.stdout, EVENT_READ)
                        assert ready.select(5), 'source descendant did not start'
                        assert child.stdout.readline().strip() == 'ready'
                # Both original owner and borrower released their descriptors.
                # Only the descendant now excludes the independent writer.
                with launcher.lock(tmp_path / 'source.lock') as writer, isolated_source.state():
                    with pytest.raises(BlockingIOError):
                        fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                child.communicate(timeout=5)
                assert child.returncode == 0
                with launcher.lock(tmp_path / 'source.lock') as writer, isolated_source.state():
                    fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                caller.communicate(timeout=5)
                if child is not None:
                    child.communicate(timeout=5)


VM_TARGETS = [(vm_name(fixture_path='common/ubuntu/common'), 'ubuntu'),
              (vm_name(fixture_path='common/fedora/common'), 'fedora')]
SYSTEM_BOOTSTRAP_ALIASES = ('check_parent_setup', 'check_parent_input',
                            'check_parent_standard_input')
PRODUCT_FREE_FIXTURE_SELECTORS = ('check_fixture_system_product_free',
                                 *SYSTEM_BOOTSTRAP_ALIASES)


@pytest.fixture
def vm_execution_branch(monkeypatch):
    """Dispatch doubles use the selected VM's branch without accessing a VM."""
    import vm_config
    branch = vm_config.load(vm_name()).owning_branch
    monkeypatch.setattr(vm_config, 'current_branch', lambda: branch)


@pytest.mark.parametrize('name,options,target,suffix,build_status', [
    ('check_e2e_gdm_recipient', {}, vm_name(0), '', 0),
    ('check_e2e_feedback_read', {'package_source': True}, vm_name(1), '.py', 7),
    ('check_e2e_read_overlay_about_and_links', {'fixture_source': True}, vm_name(1), '.py', 0),
    ('check_e2e_upgrade_assets', {'upgrade_source': True}, vm_name(0), '', 7),
    ('check_e2e_update_no_action', {'no_action_source': True}, vm_name(0), '', 0),
    ('check_e2e_activation_process', {'process_source': True}, vm_name(0), '', 0),
    ('check_e2e_activation_session', {'session_source': True}, vm_name(0), '', 0),
    ('check_e2e_kiosk_eligible_choices', {'vm_source': True, 'fixture_source': True},
     vm_name(0), '', 0),
    ('check_fixture_system_installed', {'vm_source': True, 'fixture_source': True},
     vm_name(1), '.py', 0),
])
def test_named_input_preparation_precedes_dispatch_and_failure_stops_privilege(
        monkeypatch, synthetic_package_identity, name, options, suffix, build_status, target):
    import dev_privileges
    import regression_process
    import test_storage

    monkeypatch.setenv('ONPC_TEST_VM', target)
    vm_args = ['--vm', target]
    output = str(test_storage.named_input(**options))
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=output)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    fixture_options = (['--fixture-selection', '{"frozen":"fixture"}']
                       if name in ('check_fixture_provisioning', 'check_fixture_system_installed',
                                   *PRODUCT_FREE_FIXTURE_SELECTORS,
                                   *commands.INSTALLED_E2E_FIXTURE_SELECTORS,
                                   'check_fixture_transfer', 'check_fixture_serial',
                                   'check_fixture_recorded_serial') else [])
    freeze = Mock(return_value=fixture_options)
    monkeypatch.setattr(commands, 'qualification_fixture_options', freeze)
    needs_snapshot = name in ('check_e2e_gdm_recipient', 'check_e2e_feedback_read',
                              'check_e2e_read_overlay_about_and_links',
                              'check_e2e_kiosk_eligible_choices')
    execute = Mock(side_effect=[build_status, *([0] if needs_snapshot else []), 0])
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    authorize = Mock()
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    selector = name + suffix
    assert regression_process.category_run(
        ROOT, 'system', [selector], pipe=False) == build_status
    allocate.assert_called_once_with(output)
    flags = (['--session-inputs'] if options.get('session_source') else
             ['--process-inputs'] if options.get('process_source') else
             ['--no-action-inputs'] if options.get('no_action_source') else
             ['--upgrade-inputs'] if options.get('upgrade_source') else [])
    assert execute.call_args_list[0].args[0] == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', *flags, '--output', output, *vm_args)
    if build_status:
        assert execute.call_count == 1
        authorize.assert_not_called()
        freeze.assert_called_once()
    else:
        assert execute.call_count == 2 + needs_snapshot
        assert [call.args for call in authorize.call_args_list] == [
            ('/usr/local/libexec/onpc-test-runner',)] * (1 + needs_snapshot)
        if needs_snapshot:
            snapshot = execute.call_args_list[1]
            assert snapshot.args[0] == [
                '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                '/usr/local/libexec/onpc-test-runner', '--unattended', 'appsnapshot',
                '--overwrite', 'false', '--artifacts', output, *vm_args]
            assert snapshot.kwargs['cooperative'] is True
        assert freeze.call_count == 1
        assert freeze.call_args.args == (ROOT, 'system', [selector])
        assert isinstance(freeze.call_args.kwargs['control'], regression_process.Control)
        assert freeze.call_args.kwargs['environment']['PYTHONUNBUFFERED'] == '1'
        assert execute.call_args.args[0] == [
            '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            '/usr/local/libexec/onpc-test-runner', '--unattended', 'system', selector, *vm_args,
            *fixture_options]


def test_fixture_qualification_refuses_other_target_before_preparing(monkeypatch):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    with pytest.raises(ValueError, match='target is unavailable'):
        commands.qualification_fixture_options(ROOT, 'system', ['check_fixture_provisioning'], control=control)
    control.run.assert_not_called()


@pytest.mark.parametrize(('category', 'arguments'), [
    ('system', ['check_fixture_transfer']),
    ('system', ['check_fixture_transfer.py']),
    ('e2e', ['--qualify-transfer']),
])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_transfer_freezes_exact_input_before_privileged_dispatch(
        monkeypatch, frozen_fixture_selection, category, arguments, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    families = json.loads((ROOT / 'config/environment.json').read_text())['families']
    fixture_path = next(family['fixture_path'] for family in families
                        if any(entry['name'] == vm for entry in family['vms']))
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
                                               '--target', target, '--fixture-path', fixture_path)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]
    assert commands.qualification_input_options(ROOT, 'check_fixture_transfer') == {
        'vm_source': True, 'fixture_source': True}


@pytest.mark.parametrize(('category', 'arguments'), [
    ('system', ['check_fixture_transfer']), ('e2e', ['--qualify-transfer']),
])
def test_transfer_refuses_unqualified_target_before_input_preparation(monkeypatch, category, arguments):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    with pytest.raises(ValueError, match='fixture transfer target is unavailable'):
        commands.qualification_fixture_options(ROOT, category, arguments, control=control)
    if category == 'system':
        with pytest.raises(ValueError, match='fixture transfer target is unavailable'):
            commands.qualification_artifact_command(ROOT, category, arguments)
    control.run.assert_not_called()


@pytest.mark.parametrize(('category', 'arguments'), [
    ('system', ['check_graphical_serial']),
    ('system', ['check_graphical_serial.py']),
    ('system', ['check_fixture_serial']),
    ('system', ['check_fixture_serial.py']),
    ('e2e', ['--qualify-install']), ('e2e', ['--qualify-install-refusal']),
])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_serial_freezes_exact_input_and_refuses_unknown_target_before_preparation(
        monkeypatch, frozen_fixture_selection, category, arguments, vm, target):
    families = json.loads((ROOT / 'config/environment.json').read_text())['families']
    fixture_path = next(family['fixture_path'] for family in families
                        if any(entry['name'] == vm for entry in family['vms']))
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
                                               '--target', target, '--fixture-path', fixture_path)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]
    if category == 'system':
        # Bare serial needs no assets; qualification retains its readback witness.
        expected = ({'vm_source': True, 'fixture_source': True}
                    if arguments[0].removesuffix('.py') == 'check_fixture_serial' else None)
        assert commands.qualification_input_options(ROOT, arguments[0]) == expected
        if expected is None:
            assert commands.qualification_artifact_command(ROOT, category, arguments) is None
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    with pytest.raises(ValueError, match='fixture serial target is unavailable'):
        commands.qualification_fixture_options(ROOT, category, arguments, control=control)
    if category == 'system':
        with pytest.raises(ValueError, match='fixture serial target is unavailable'):
            commands.qualification_artifact_command(ROOT, category, arguments)
    control.run.assert_not_called()


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_recorded_serial_freezes_exact_input_before_dispatch(
        monkeypatch, frozen_fixture_selection, suffix, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    families = json.loads((ROOT / 'config/environment.json').read_text())['families']
    fixture_path = next(family['fixture_path'] for family in families
                        if any(entry['name'] == vm for entry in family['vms']))
    selector = 'check_fixture_recorded_serial' + suffix
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
                                               '--target', target, '--fixture-path', fixture_path)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, 'system', [selector],
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]
    assert commands.qualification_input_options(ROOT, selector) == {
        'vm_source': True, 'fixture_source': True}


@pytest.mark.parametrize('suffix', ['', '.py'])
def test_recorded_serial_refuses_before_input_preparation(monkeypatch, suffix):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    selector = 'check_fixture_recorded_serial' + suffix
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'system', [selector]),
            lambda: commands.qualification_artifact_command(ROOT, 'system', [selector]),
            lambda: commands.qualification_fixture_options(
                ROOT, 'system', [selector], control=control)):
        with pytest.raises(ValueError, match='fixture recorded serial target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize('selector', PRODUCT_FREE_FIXTURE_SELECTORS)
@pytest.mark.parametrize('suffix', ['', '.py'])
def test_product_free_fixture_target_refuses_before_package_or_fixture_input(monkeypatch, selector, suffix):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'system', [selector + suffix]),
            lambda: commands.qualification_artifact_command(ROOT, 'system', [selector + suffix]),
            lambda: commands.qualification_fixture_options(
                ROOT, 'system', [selector + suffix], control=control)):
        with pytest.raises(ValueError, match='target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize(('category', 'arguments'), [
    *(('system', [name]) for name in PRODUCT_FREE_FIXTURE_SELECTORS),
    ('system', ['--area=lifecycle', '--test=first-configure', '--previous-artifacts=/tmp/onpc-previous']),
])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_product_free_runner_freezes_exact_input_before_dispatch(
        monkeypatch, category, arguments, frozen_fixture_selection, vm, target):
    import vm_selection
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    fixture_path = vm_selection.selected().fixture_path
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    source_edit = arguments == ['check_fixture_system_product_free']
    source = source_proof_selection(frozen_fixture_selection)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py', '--target', target,
                                               '--fixture-path', fixture_path,
                                               *(['--qualify-source-edit'] if source_edit else []))
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        if source_edit:
            options['output'](('fixture-execution: source-edit=' + json.dumps(source) + '\n').encode())
        return 0
    control = SimpleNamespace(run=Mock(side_effect=execute))
    original = list(arguments)
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=control, environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True),
            *(['--fixture-source-selection', json.dumps(source, sort_keys=True)] if source_edit else [])]
    assert arguments == original
    control.run.assert_called_once()


@pytest.mark.parametrize(('category', 'arguments'), [
    *(('system', [name]) for name in PRODUCT_FREE_FIXTURE_SELECTORS),
    ('system', ['--artifacts=/tmp/onpc-packages', '--previous-artifacts=/tmp/onpc-previous',
                '--area=lifecycle', '--test=first-configure']),
])
@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_product_free_dispatcher_preserves_the_frozen_record(
        monkeypatch, category, arguments, frozen_fixture_selection, suffix, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    record = frozen_fixture_selection.record()
    encoded = json.dumps(record)
    source_options = (['--fixture-source-selection', json.dumps(source_proof_selection(frozen_fixture_selection))]
                      if arguments == ['check_fixture_system_product_free'] else [])
    selected_arguments = ([arguments[0] + suffix] if commands.system_check_selection(arguments) else arguments)
    command = dispatch(ROOT, [category, *selected_arguments, '--fixture-selection', encoded,
                              *source_options, '--vm', vm])
    index = command.index('--fixture-selection')
    assert json.loads(command[index + 1]) == record
    if source_options:
        assert json.loads(command[command.index('--fixture-source-selection') + 1]) == source_proof_selection(frozen_fixture_selection)
    if not commands.system_check_selection(arguments):
        assert command[-2:] == ['--area=lifecycle', '--test=first-configure']
        for option in ('--artifacts', '--previous-artifacts'):
            assert command[command.index(option) + 1] in ('/tmp/onpc-packages', '/tmp/onpc-previous')


@pytest.mark.parametrize('selector', ['check_fixture_provisioning', *SYSTEM_BOOTSTRAP_ALIASES, 'check_future_feature'])
@pytest.mark.parametrize('vm', [vm_name(0), vm_name(1)])
def test_source_proof_option_refuses_other_system_checks(monkeypatch, selector, frozen_fixture_selection, vm):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    with pytest.raises(ValueError, match='unexpected-fixture-source-selection'):
        dispatch(ROOT, ['system', selector, '--vm', vm,
                        '--fixture-selection', json.dumps(frozen_fixture_selection.record()),
                        '--fixture-source-selection', json.dumps(source_proof_selection(frozen_fixture_selection))])


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_installed_system_freezes_original_input_and_actual_source_proof(
        monkeypatch, frozen_fixture_selection, suffix, vm, target):
    import vm_selection
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    fixture_path = vm_selection.selected().fixture_path
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    source = source_proof_selection(frozen_fixture_selection)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
            '--target', target, '--fixture-path', fixture_path, '--qualify-source-edit')
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n'
            + 'fixture-execution: source-edit=' + json.dumps(source) + '\n').encode())
        return 0
    control = SimpleNamespace(run=Mock(side_effect=execute))
    options = commands.qualification_fixture_options(ROOT, 'system',
        ['check_fixture_system_installed' + suffix], control=control, environment={})
    assert options == ['--fixture-selection', json.dumps(record, sort_keys=True),
                       '--fixture-source-selection', json.dumps(source, sort_keys=True)]
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    command = dispatch(ROOT, ['system', 'check_fixture_system_installed' + suffix,
                              '--vm', vm, *options])
    assert command[3:] == options


@pytest.mark.parametrize('vm', ['unqualified-target'])
@pytest.mark.parametrize('suffix', ['', '.py'])
def test_installed_system_target_refuses_before_any_input(monkeypatch, vm, suffix):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name=vm))
    selector = 'check_fixture_system_installed' + suffix
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'system', [selector]),
            lambda: commands.qualification_artifact_command(ROOT, 'system', [selector]),
            lambda: commands.qualification_fixture_options(
                ROOT, 'system', [selector], control=control)):
        with pytest.raises(ValueError, match='target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'foreign-input', 'oversized', 'malformed'])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_source_proof_handoff_requires_one_bound_record(monkeypatch, fault, frozen_fixture_selection, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    source = source_proof_selection(frozen_fixture_selection)
    if fault == 'foreign-input':
        source['build_identity'] = 'f' * 64
    line = b'fixture-execution: source-edit=' + json.dumps(source).encode() + b'\n'
    line = {'missing': b'', 'duplicate': line * 2,
            'oversized': b'fixture-execution: source-edit=' + b'x' * 8193 + b'\n',
            'malformed': b'fixture-execution: source-edit={\n'}.get(fault, line)
    def execute(command, **options):
        options['output'](b'fixture-execution: selection=' + json.dumps(record).encode() + b'\n' + line)
        return 0
    with pytest.raises(ValueError):
        commands.qualification_fixture_options(ROOT, 'system', ['check_fixture_system_product_free'],
            control=SimpleNamespace(run=execute), environment={})


@pytest.mark.parametrize('category,arguments', [
    *(('system', [name]) for name in PRODUCT_FREE_FIXTURE_SELECTORS),
    ('system', ['--artifacts=/tmp/onpc-packages']),
])
@pytest.mark.parametrize(('vm', 'target'), [(vm, 'fedora' if target == 'ubuntu' else 'ubuntu')
                                          for vm, target in VM_TARGETS])
def test_dispatcher_refuses_foreign_product_free_fixture_target(
        monkeypatch, category, arguments, frozen_fixture_selection, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    with pytest.raises(ValueError, match='fixture-target-not-qualified'):
        dispatch(ROOT, [category, *arguments, '--fixture-selection',
                        json.dumps(frozen_fixture_selection.record()), '--vm', vm])


@pytest.fixture
def frozen_fixture_selection(monkeypatch):
    from tools import fixture_execution
    from vm_selection import vm_config
    branch = vm_config.current_branch()
    monkeypatch.setattr(vm_config, 'current_branch', lambda: branch)
    return fixture_execution.Selection('ubuntu', 'a' * 64,
        '/tmp/onpc-native-runtime-ubuntu-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64)


def source_proof_selection(selected):
    return selected.record() | {'allocation': '/tmp/onpc-fixture-source-edit-private',
                                'device': 5, 'inode': 6}


@pytest.mark.parametrize(('action', 'status'), [('start', 0), ('start', 7), ('sync-fixtures', 0)])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_public_fixture_maintenance_keeps_one_selector_and_pins_sync_input(
        monkeypatch, frozen_fixture_selection, action, status, vm, target):
    from contextlib import contextmanager
    import dev_privileges
    import fixture_execution
    import test_retention
    import test_storage
    import vm_pool
    configured = SimpleNamespace(name=vm, fixture_path='selected-fixtures')
    monkeypatch.setattr(dev_privileges, 'check', Mock())
    reserved = []
    @contextmanager
    def reservation(name):
        assert name == vm and not reserved
        reserved.append(name)
        try:
            yield
        finally:
            assert not active
            reserved.pop()
    monkeypatch.setattr(vm_pool, 'reservation', reservation)
    def checkout_arguments():
        assert reserved == [vm]
        return ['--vm-checkout=receipt']
    monkeypatch.setattr(vm_pool, 'arguments', checkout_arguments)
    monkeypatch.setattr(test_storage, 'directory', lambda kind: ROOT / 'unused-state')
    active = []
    sessions = []
    @contextmanager
    def session(**kwargs):
        assert reserved == [vm]
        sessions.append(kwargs)
        active.append(True)
        try:
            yield
        finally:
            active.pop()
    @contextmanager
    def opened():
        assert reserved == [vm]
        yield 12
    store = SimpleNamespace(session=session, opened=opened,
                            read=lambda fd: {'run': 'b' * 32})
    def make_store(path):
        assert reserved == [vm]
        return store
    monkeypatch.setattr(test_retention, 'Store', make_store)
    def prepare(**kwargs):
        assert active and kwargs == {'target': target,
                                     'fixture_path': configured.fixture_path}
        return frozen_fixture_selection
    monkeypatch.setattr(fixture_execution, 'prepare', prepare)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert command.count('--vm') == 1
        assert command[3] == '--vm-checkout=receipt'
        assert bool(active) == (action == 'sync-fixtures')
        return SimpleNamespace(returncode=status)
    monkeypatch.setattr(subprocess, 'run', run)
    function = runpy.run_path(str(ROOT / 'tools/test-vm'))['fixture_maintenance']
    options = ['start', '--fixture-maintenance'] if action == 'start' else [action]
    assert function(options, configured) == status
    assert len(calls) == 1
    assert not reserved
    assert sessions == ([{}] if action == 'start' and status == 0 else
                        [{'run': 'b' * 32}] if action == 'sync-fixtures' else [])


@pytest.mark.parametrize('failure', [None, 'retain-a', 'build-b', 'replace-b'])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_live_refresh_orders_actual_a_use_before_b_build_and_recovers_failures(
        monkeypatch, frozen_fixture_selection, failure, vm, target):
    import dev_privileges
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    monkeypatch.setattr(dev_privileges, 'check', Mock())
    original = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-'))
    replacement = replace(original, key='d' * 64, build_identity='e' * 64,
        allocation=original.allocation.replace('a' * 64, 'd' * 64))
    source = source_proof_selection(original)
    events = []

    def run(command, **kwargs):
        if '--live-refresh-source' in command:
            assert command[command.index('--target') + 1] == target
            events.append('build-a')
            kwargs['output'](b'fixture-execution: selection=' + json.dumps(original.record()).encode() + b'\n')
            kwargs['output'](b'fixture-execution: source-edit=' + json.dumps(source).encode() + b'\n')
        elif '--live-refresh-selection' in command:
            assert command[command.index('--target') + 1] == target
            assert events == ['build-a', 'retain-a']
            events.append('build-b')
            if failure == 'build-b':
                return 7
            kwargs['output'](b'fixture-execution: selection=' + json.dumps(replacement.record()).encode() + b'\n')
        elif command[-1] == 'retain-a':
            events.append('retain-a')
            if failure == 'retain-a':
                return 8
        else:
            events.append('replace-b')
            assert json.loads(command[command.index('--fixture-replacement-selection') + 1]) == replacement.record()
            if failure == 'replace-b':
                return 9
        return 0

    cleanup = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(commands.subprocess, 'run', cleanup)
    control = SimpleNamespace(run=run)
    command = ['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner',
               'system', 'check_fixture_live_refresh', '--vm', vm]
    if failure == 'build-b':
        with pytest.raises(ValueError, match='preparation failed'):
            commands.run_live_refresh(ROOT, command, control=control, environment={})
    else:
        assert commands.run_live_refresh(ROOT, command, control=control, environment={}) == (
            8 if failure == 'retain-a' else 9 if failure else 0)
    assert events[:2] == ['build-a', 'retain-a']
    if failure != 'retain-a':
        assert events[:3] == ['build-a', 'retain-a', 'build-b']
    assert cleanup.call_count == (1 if failure in ('build-b', 'replace-b') else 0)
    if failure in ('build-b', 'replace-b'):
        assert cleanup.call_args.args[0][-4:] == ['vm', '--vm', vm, 'stop']


@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
@pytest.mark.parametrize('selector', ['check_fixture_e2e_installed', 'check_fixture_e2e_product_free'])
def test_e2e_qualification_freezes_input_and_source_proof(monkeypatch, frozen_fixture_selection, vm, target, selector):
    import vm_selection
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    fixture_path = vm_selection.selected().fixture_path
    selected = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-'))
    record = selected.record()
    source = source_proof_selection(selected)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
            '--target', target, '--fixture-path', fixture_path, '--qualify-source-edit')
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n'
            + 'fixture-execution: source-edit=' + json.dumps(source) + '\n').encode())
        return 0
    options = commands.qualification_fixture_options(ROOT, 'system',
        [selector], control=SimpleNamespace(run=execute), environment={})
    assert options == ['--fixture-selection', json.dumps(record, sort_keys=True),
                       '--fixture-source-selection', json.dumps(source, sort_keys=True)]
    assert commands.qualification_input_options(ROOT, selector) == {
        'vm_source': True, 'fixture_source': True,
        **({'upgrade_source': True} if selector == 'check_fixture_e2e_product_free' else {})}
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    command = dispatch(ROOT, ['system', selector,
                             '--vm', vm, *options])
    assert command[3:] == options


@pytest.mark.parametrize(('category', 'arguments'), [
    ('system', ['check_e2e_approval_flow']),
    ('system', ['check_e2e_time_profiles_daily']),
    ('system', ['check_e2e_native_fixtures']),
    ('system', ['check_e2e_game_fixture']),
    ('e2e', ['--ready']),
])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_installed_e2e_freezes_before_privileged_dispatch(
        monkeypatch, frozen_fixture_selection, category, arguments, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    families = json.loads((ROOT / 'config/environment.json').read_text())['families']
    fixture_path = next(family['fixture_path'] for family in families
                        if any(entry['name'] == vm for entry in family['vms']))
    record = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-')).record()
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
            '--target', target, '--fixture-path', fixture_path)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]


@pytest.mark.parametrize('selector', ['check_fixture_e2e_installed', 'check_e2e_approval_flow'])
def test_installed_e2e_refuses_unqualified_target_before_preparing(monkeypatch, selector):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified'))
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'system', [selector]),
            lambda: commands.qualification_artifact_command(ROOT, 'system', [selector]),
            lambda: commands.qualification_fixture_options(ROOT, 'system', [selector], control=control)):
        with pytest.raises(ValueError, match='installed E2E target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_e2e_preflight_preserves_frozen_selection_without_opening_bundle(
        monkeypatch, frozen_fixture_selection, vm, target):
    namespace = runpy.run_path(str(ROOT / 'tests/e2e/runner.py'))
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    preflight = namespace['preflight']
    monkeypatch.setattr(namespace['password_config'], 'read_password', Mock())
    declarations = {
        'read_json': lambda path: ({}, 'd' * 64),
        'resolve_selection': lambda *args, **kwargs: {'cases': [], 'selector': 'selected'},
    }
    monkeypatch.setattr(namespace['runpy'], 'run_path', lambda path: (
        {'preflight': preflight} if str(path).endswith('/tests/e2e/runner.py') else declarations))
    record = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-')).record()
    plan = preflight(['--ready', '--vm', vm,
                      '--fixture-selection', json.dumps(record)], allow_missing_artifacts=True)
    assert plan['fixture_selection'] == record
    assert plan['mode'] == 'execution-preflight'
    command = dispatch(ROOT, ['e2e', '--ready', '--vm', vm,
                       '--fixture-selection', json.dumps(record)], allow_missing_artifacts=True)
    assert command[-2:] == ['--fixture-selection', json.dumps(record, sort_keys=True)]


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_fixture_qualification_forwards_exact_frozen_selection(monkeypatch, suffix, vm, target, frozen_fixture_selection):
    import vm_selection
    fixture_path = 'selected-fixtures'
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(
        name=vm, fixture_path=fixture_path))
    selected = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    encoded = b'fixture-execution: selection=' + json.dumps(selected.record()).encode() + b'\n'

    def execute(command, **kwargs):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
            '--target', target, '--fixture-path', fixture_path)
        assert kwargs['cwd'] == ROOT and kwargs['env'] == {'PRIVATE': 'environment'}
        assert kwargs['timeout'] == 600.0
        # Split both the prefix and the JSON across callback invocations.
        for chunk in (b'producer progress\n', encoded[:7], encoded[7:42], encoded[42:]):
            kwargs['output'](chunk)
        return 0

    control = SimpleNamespace(run=Mock(side_effect=execute))
    assert commands.qualification_fixture_options(ROOT, 'system',
        ['check_fixture_provisioning' + suffix], control=control,
        environment={'PRIVATE': 'environment'}) == [
            '--fixture-selection', json.dumps(selected.record(), sort_keys=True)]
    control.run.assert_called_once()


@pytest.mark.parametrize('failure', ['missing', 'duplicate', 'malformed', 'oversized',
    'unterminated', 'foreign-target', 'nonzero'])
@pytest.mark.parametrize(('vm', 'target'), VM_TARGETS)
def test_fixture_qualification_rejects_invalid_child_result(monkeypatch, frozen_fixture_selection, failure, vm, target):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(
        name=vm, fixture_path='selected-fixtures'))
    record = frozen_fixture_selection.record()
    record['target'] = target
    record['allocation'] = record['allocation'].replace('ubuntu', target)
    if failure == 'foreign-target':
        foreign = 'fedora' if target == 'ubuntu' else 'ubuntu'
        record['target'] = foreign
        record['allocation'] = record['allocation'].replace(target, foreign)
    line = b'fixture-execution: selection=' + json.dumps(record).encode() + b'\n'
    output = {'missing': b'progress only\n', 'duplicate': line * 2,
        'malformed': b'fixture-execution: selection={\n',
        'oversized': b'fixture-execution: selection=' + b'x' * 8193 + b'\n',
        'unterminated': line.rstrip(b'\n')}.get(failure, line)

    def execute(command, **kwargs):
        kwargs['output'](output)
        return 9 if failure == 'nonzero' else 0

    control = SimpleNamespace(run=Mock(side_effect=execute))
    with pytest.raises(ValueError):
        commands.qualification_fixture_options(ROOT, 'system',
            ['check_fixture_provisioning'], control=control, environment={})
    control.run.assert_called_once()


@pytest.mark.parametrize('route', ['category', 'direct'])
@pytest.mark.parametrize('failure', ['none', 'package', 'fixture', 'malformed', 'duplicate'])
def test_fixture_qualification_freezes_before_package_and_privilege(
        monkeypatch, route, failure, frozen_fixture_selection):
    import dev_privileges
    import regression_process
    import vm_selection
    events = []
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(
        name=vm_name(0), fixture_path='selected-fixtures'))
    monkeypatch.setattr(commands, 'plan', lambda *args: (
        [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner',
          'system', 'check_fixture_provisioning']], False))
    package_command = ['package-preparation', '--output', '/tmp/onpc-test-input']
    monkeypatch.setattr(commands, 'qualification_artifact_command', lambda *args: package_command)
    monkeypatch.setattr(commands, 'qualification_input_options', lambda *args: {})
    monkeypatch.setattr('test_storage.named_input', lambda **kwargs: commands.Path('/tmp/onpc-test-input'))
    frozen = frozen_fixture_selection.record()
    monkeypatch.setattr(dev_privileges, 'check', lambda *args: events.append('privilege'))
    executed = []

    def execute(command, **kwargs):
        executed.append(command)
        if 'tools/fixture_execution.py' in ' '.join(command):
            events.append('fixture')
            line = b'fixture-execution: selection=' + json.dumps(frozen).encode() + b'\n'
            if failure == 'malformed':
                line = b'fixture-execution: selection={\n'
            elif failure == 'duplicate':
                line *= 2
            kwargs['output'](line)
            return 9 if failure == 'fixture' else 0
        events.append('package' if command == package_command else 'dispatch')
        status = 7 if command == package_command and failure == 'package' else 0
        return status

    control = SimpleNamespace(run=Mock(side_effect=execute))
    monkeypatch.setattr(regression_process.Control, 'installed', Mock(return_value=nullcontext(control)))
    if route == 'category':
        run = lambda: regression_process.category_run(
            ROOT, 'system', ['check_fixture_provisioning'], pipe=False)
        if failure in ('fixture', 'malformed', 'duplicate'):
            with pytest.raises(ValueError):
                run()
        else:
            assert run() == (7 if failure == 'package' else 0)
    else:
        monkeypatch.setattr(commands, 'vm_request', lambda argv: (argv, None))
        monkeypatch.setattr(commands, 'host_only_request', lambda argv: True)
        monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
        monkeypatch.setattr(commands.os, 'chdir', Mock())
        import test_storage
        descriptors = (71, 72)
        monkeypatch.setattr(test_storage, 'scratch_descriptors', lambda: descriptors)

        def run(command, **kwargs):
            assert kwargs['pass_fds'] == descriptors
            return SimpleNamespace(returncode=execute(command, **kwargs))

        monkeypatch.setattr(commands.subprocess, 'run', run)
        assert commands._main(['system', 'check_fixture_provisioning']) == (
            {'package': 7, 'fixture': 2, 'malformed': 2, 'duplicate': 2}.get(failure, 0))
    if failure == 'package':
        assert events == ['fixture', 'package']
    elif failure in ('fixture', 'malformed', 'duplicate'):
        assert events == ['fixture']
    else:
        assert events == ['fixture', 'package', 'privilege', 'dispatch']
        assert executed[-1][-2:] == ['--fixture-selection', json.dumps(frozen, sort_keys=True)]


@pytest.mark.parametrize('options', [
    ['build', '--kind', 'native-runtime'],
    ['build', '--kind', 'native-runtime', '--target', 'other'],
    ['build', '--kind', 'native-runtime', '--target', 'ubuntu', '--output', '/elsewhere'],
    ['verify', '--kind', 'native-runtime', '--target', 'ubuntu'],
    ['build', '--target', 'ubuntu', '--kind', 'native-runtime'],
    ['recover'],
    ['recover', '/elsewhere'],
    ['recover', '1' * 32, '2' * 32],
])
def test_native_fixture_options_refuse_before_allocating(options):
    with pytest.raises(ValueError):
        commands.plan(ROOT, 'fixtures', options)


def test_fixture_recovery_forwards_only_the_exact_transaction():
    planned, privileged = commands.plan(ROOT, 'fixtures', ['recover', '1' * 32])
    assert planned == [commands.python_file(
        ROOT, 'tools/fixture_producer.py', '--recover', '1' * 32)]
    assert privileged is False


def test_native_fixture_category_registers_build_output_before_execution(monkeypatch, tmp_path):
    import regression_process
    output = str(tmp_path)
    allocation = Mock(return_value=output)
    monkeypatch.setattr(regression_process.Control, 'run', Mock(return_value=0))
    import test_retention
    monkeypatch.setattr(test_retention, 'allocate', allocation)
    assert regression_process.category_run(ROOT, 'fixtures',
        ['build', '--kind', 'native-runtime', '--target', 'ubuntu'], pipe=False) == 0
    assert allocation.call_count == 1
    assert regression_process.Control.run.call_args.args[0] == commands.python_file(
        ROOT, 'tools/fixture_bundle.py', '--target', 'ubuntu', '--output', output)


@pytest.mark.parametrize('status,package_format', [(3, 'deb'), (5, 'rpm'), (6, None), (0, None), (130, None)])
@pytest.mark.parametrize('candidate_format', [None, 'deb', 'rpm'])
def test_vm_artifacts_use_verified_platform_and_preserve_probe_failures(
        tmp_path, monkeypatch, capsys, status, package_format, candidate_format):
    import vm_artifacts
    import build_test_artifacts
    family = 'fedora44-x86_64' if package_format == 'rpm' else 'ubuntu26.04-x86_64'
    configured = replace(vm_artifacts.selected(), family=family, package_format=package_format or 'deb')
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: configured)
    target = configured.require_build_target()
    output = tmp_path / 'output'
    candidate = tmp_path / 'candidate' if candidate_format else None
    verify = Mock(return_value={'artifacts': {'package': {'path': 'app.' + str(candidate_format)}},
                              'build_inputs': {'build_target': target.name,
                                               'target_architecture': target.architecture}})
    monkeypatch.setattr(build_test_artifacts, 'verify', verify)
    verify_target = Mock()
    monkeypatch.setattr(build_test_artifacts, 'verify_package_target', verify_target)
    authorize = Mock()
    monkeypatch.setattr(vm_artifacts, 'check', authorize)
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    control = Mock()
    control.run.side_effect = [status, 0]
    result = vm_artifacts.prepare(ROOT, control, {}, candidate=candidate)
    authorize.assert_called_once_with('/usr/local/libexec/onpc-test-runner')
    assert control.run.call_args_list[0].args[0] == [
        '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
        '/usr/local/libexec/onpc-test-runner', 'appsnapshot', '--probe',
        '--overwrite', 'true', *VM_ARGS]
    if package_format is None:
        assert result == (status or 2)
        assert control.run.call_count == 1
        allocate.assert_not_called()
        verify.assert_not_called()
    elif candidate_format == package_format:
        assert result == 0 and control.run.call_count == 1
        allocate.assert_not_called()
        verify.assert_called_once_with(candidate)
        verify_target.assert_called_once_with(candidate / f'app.{candidate_format}', target,
                                             build_inputs=verify.return_value['build_inputs'])
        assert capsys.readouterr().out.strip() == 'run-tests: output=' + str(candidate)
    else:
        assert result == 0
        assert control.run.call_args.args[0] == [
            '/usr/bin/python3', '-B', str(ROOT / 'tools/build_test_artifacts.py'),
            '--reuse', '--package-format', package_format, '--build-target', target.name,
            '--architecture', target.architecture, '--output', str(output)]
        allocate.assert_called_once()


@pytest.mark.parametrize('options', [
    ['prepare', '--upgrade-inputs'],
    ['prepare', '--for-vm', '--upgrade-inputs', '--upgrade-inputs'],
    ['prepare', '--for-vm', '--upgrade-inputs', '--unknown'],
])
def test_upgrade_preparation_rejects_unvalidated_option_shapes(options):
    with pytest.raises(ValueError, match='invalid artifact operation'):
        commands.plan(ROOT, 'artifacts', options)


@pytest.mark.parametrize('status,package_format', [(3, 'deb'), (5, 'rpm')])
@pytest.mark.parametrize('candidate', [False, True])
def test_vm_upgrade_preparation_uses_verified_format_and_owned_allocation(
        tmp_path, monkeypatch, status, package_format, candidate):
    import vm_artifacts
    import build_test_artifacts
    family = 'fedora46_x86_64' if package_format == 'rpm' else 'ubuntu26.10_x86_64'
    configured = replace(vm_artifacts.selected(), family=family, package_format=package_format)
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: configured)
    target = configured.require_build_target()
    monkeypatch.setattr(vm_artifacts, 'check', Mock())
    output = tmp_path / 'output'
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    verify = Mock(return_value={'packages': {'current': {
        'architecture': {'deb': 'amd64', 'rpm': 'x86_64'}[package_format],
        'version': '1.4-0.1.dev.fc46' if package_format == 'rpm' else '1.4+local1~ubuntu26.10.1'}}})
    monkeypatch.setattr(build_test_artifacts, 'verify_upgrade', verify)
    control = Mock()
    control.run.side_effect = [status, 0]
    assert vm_artifacts.prepare(ROOT, control, {}, upgrade_inputs=True,
                                candidate=output if candidate else None) == 0
    if candidate:
        verify.assert_called_once_with(output)
        allocate.assert_not_called()
        assert control.run.call_count == 1
    else:
        allocate.assert_called_once_with(vm_artifacts.tempfile.mkdtemp, prefix='onpc-test-artifacts-')
        verify.assert_not_called()
        assert control.run.call_args.args[0] == [
            '/usr/bin/python3', '-B', str(ROOT / 'tools/build_test_artifacts.py'),
            '--upgrade-inputs', '--package-format', package_format, '--build-target', target.name,
            '--architecture', target.architecture, '--output', str(output)]


@pytest.mark.parametrize('declared,baseline', [('deb', 5), ('rpm', 3), (None, 5)])
def test_vm_preparation_never_defaults_or_builds_for_mismatched_configuration(
        tmp_path, monkeypatch, declared, baseline):
    import vm_artifacts
    family = 'fedora44-x86_64' if declared == 'rpm' else 'ubuntu26.04-x86_64'
    configured = replace(vm_artifacts.selected(), family=family, package_format=declared)
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: configured)
    authorize = Mock()
    monkeypatch.setattr(vm_artifacts, 'check', authorize)
    allocate = Mock(side_effect=AssertionError('invalid declaration allocated output'))
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    control = Mock()
    control.run.return_value = baseline
    if declared is None:
        with pytest.raises(ValueError, match='package_format'):
            vm_artifacts.prepare(ROOT, control, {})
        authorize.assert_not_called()
        control.run.assert_not_called()
    else:
        assert vm_artifacts.prepare(ROOT, control, {}) == 2
        assert control.run.call_count == 1
    allocate.assert_not_called()


@pytest.mark.parametrize('status', [0, 7, 130])
@pytest.mark.parametrize('equal_form', [False, True])
def test_focused_system_prepares_private_inputs_preserving_selectors_and_guards(
        monkeypatch, status, equal_form, frozen_fixture_selection):
    import dev_privileges
    import regression_process
    import test_retention

    selectors = (['--area=authorization', '--test=case[param]'] if equal_form else
                 ['--area', 'authorization', '--test', 'case[param]'])
    previous = '/tmp/onpc-previous'
    args = [*selectors, '--previous-artifacts', previous,
            '--completed-cases=["prior-case"]', '--qualification-failure', '--skip-backing-verification']
    # The real checkout preflight validates all options before allocating inputs.
    planned, _ = commands.plan(ROOT, 'system', args)
    assert not commands.has_artifacts(planned[0])
    output = '/tmp/onpc-focused-system'
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    monkeypatch.setattr(test_retention, 'token', lambda: 'a' * 32)
    authorize = Mock()
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    frozen = ['--fixture-selection', json.dumps(frozen_fixture_selection.record(), sort_keys=True)]
    freeze = Mock(return_value=frozen)
    monkeypatch.setattr(commands, 'qualification_fixture_options', freeze)
    execute = Mock(side_effect=[status, 0])
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'system', args, pipe=False) == status
    allocate.assert_called_once()
    assert 'dir' not in allocate.call_args.kwargs
    assert execute.call_args_list[0].args[0] == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', '--output', str(output), *VM_ARGS)
    if status:
        assert execute.call_count == 1
        authorize.assert_not_called()
        freeze.assert_not_called()
    else:
        authorize.assert_called_once_with('/usr/local/libexec/onpc-test-runner')
        assert execute.call_args.args[0] == [
            '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            '/usr/local/libexec/onpc-test-runner', '--retention-run=' + 'a' * 32,
            '--unattended', 'system', *args, '--artifacts=' + str(output), *VM_ARGS, *frozen]
        assert freeze.call_args.args == (ROOT, 'system', args)
        assert execute.call_args.kwargs['cooperative'] is True


@pytest.mark.parametrize('equal_form', [False, True])
def test_focused_system_preserves_explicit_artifact_input_without_building(monkeypatch, equal_form):
    import dev_privileges
    import regression_process
    import test_retention

    artifact = '/tmp/onpc-explicit'
    args = [*(('--artifacts=' + artifact,) if equal_form else ('--artifacts', artifact)),
            '--area=authorization', '--test=case[param]']
    monkeypatch.setattr(test_retention, 'allocate', Mock(side_effect=AssertionError('replaced explicit input')))
    monkeypatch.setattr(dev_privileges, 'check', Mock())
    monkeypatch.setattr(commands, 'qualification_fixture_options', Mock(return_value=[]))
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'system', args, pipe=False) == 0
    execute.assert_called_once()
    assert execute.call_args.args[0][0] == '/usr/bin/pkexec'
    assert args == execute.call_args.args[0][-len(args) - len(VM_ARGS):-len(VM_ARGS)]


@pytest.mark.parametrize('target', [vm_name(0), vm_name(1)])
@pytest.mark.parametrize('status', [0, 7, 130])
def test_shared_upgrade_preparation_binds_each_vm_before_existing_system_dispatch(
        monkeypatch, target, status):
    import dev_privileges
    import regression_process
    import test_retention

    monkeypatch.setenv('ONPC_TEST_VM', target)
    output = str(ROOT / 'output/test-runs/host/allocations/onpc-upgrade-input')
    monkeypatch.setattr(test_retention, 'allocate', Mock(return_value=output))
    monkeypatch.setattr(test_retention, 'token', lambda: None)
    authorize = Mock()
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    monkeypatch.setattr(commands, 'qualification_fixture_options', Mock(return_value=[]))
    execute = Mock(side_effect=[status, 0])
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    args = ['--id', '287', '--upgrade-inputs']
    assert regression_process.category_run(ROOT, 'system', args, pipe=False) == status
    assert execute.call_args_list[0].args[0] == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', '--upgrade-inputs', '--output', output,
        '--vm', target)
    if status:
        assert execute.call_count == 1
        authorize.assert_not_called()
    else:
        assert execute.call_args.args[0] == [
            '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            '/usr/local/libexec/onpc-test-runner', '--unattended', 'system',
            '--id', '287', '--artifacts=' + output + '/current',
            '--previous-artifacts=' + output + '/previous', '--vm', target]


@pytest.mark.parametrize('category,args', [
    ('system', ['--upgrade-inputs', '--upgrade-inputs']),
    ('system', ['--upgrade-inputs', '--artifacts=/tmp/onpc-explicit']),
    ('system', ['--upgrade-inputs', '--previous-artifacts', '/tmp/onpc-explicit']),
    ('e2e', ['--upgrade-inputs']),
    ('system', ['check_e2e_package_upgrade', '--upgrade-inputs']),
])
def test_shared_upgrade_preparation_refuses_conflicts_before_allocation(monkeypatch, category, args):
    import regression_process
    import test_retention

    allocate = Mock(side_effect=AssertionError('invalid request allocated inputs'))
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    with pytest.raises(ValueError, match=('package history inputs cannot select a named system check'
                                         if commands.system_check_selection(args) else 'upgrade inputs require')):
        regression_process.category_run(ROOT, category, args, pipe=False)
    allocate.assert_not_called()


def test_dispatcher_still_requires_artifacts_for_actual_system_execution():
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    args = ['system', '--area=authorization', '--test=case[param]', *VM_ARGS]
    with pytest.raises(ValueError, match='test-runner:invalid-arguments'):
        dispatcher['selection'](ROOT, args)
    prepared = dispatcher['selection'](ROOT, args, allow_missing_artifacts=True)
    assert prepared[-2:] == ['--area=authorization', '--test=case[param]']


@pytest.mark.parametrize('args', [
    ['--area='], ['--test=bad\nselector'], ['--unknown'], ['--artifacts=relative'],
    ['--previous-artifacts=relative'], ['--completed-cases=invalid'],
])
def test_invalid_focused_system_selection_refuses_before_package_preparation(monkeypatch, args):
    import regression_process
    execute = Mock(side_effect=AssertionError('invalid selection started preparation'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError):
        regression_process.category_run(ROOT, 'system', args, pipe=False)
    execute.assert_not_called()


@pytest.mark.parametrize('args', [
    ['--id='], ['--id=0'], ['--id=01'], ['--id=1,1'], ['--id=999999'],
    ['--id=1,'], ['--id=1, 6'], ['--id=1', '--area=package'],
    ['--id=1', '--test=test_installed_package'], ['--id=1', '--id=6'],
])
def test_invalid_numeric_system_ids_refuse_before_inputs_or_privilege(monkeypatch, args):
    import regression_process
    import dev_privileges
    import test_retention
    execute = Mock(side_effect=AssertionError('invalid IDs launched a child'))
    allocate = Mock(side_effect=AssertionError('invalid IDs allocated artifacts'))
    authorize = Mock(side_effect=AssertionError('invalid IDs checked privilege'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    with pytest.raises(ValueError):
        regression_process.category_run(ROOT, 'system', args, pipe=False)
    execute.assert_not_called()
    allocate.assert_not_called()
    authorize.assert_not_called()


@pytest.mark.parametrize('args', [['--id', '26,6'], ['--id=26,6']])
def test_numeric_system_dispatch_preserves_explicit_ids_for_runner_resolution(args):
    planned, _ = commands.plan(ROOT, 'system', [*args, '--list'])
    assert '--id=26,6' in planned[0] and '--list' in planned[0]
    assert not any(arg.startswith(('--area', '--test=')) for arg in planned[0])


def test_named_vm_preparation_registers_before_platform_builder(monkeypatch):
    import regression_process
    output = str(ROOT / 'output/test-runs/host/allocations/onpc-native-diagnosis-input')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    args = ['prepare', '--for-vm', '--output', output]
    planned, safety = commands.plan(ROOT, 'artifacts', args)
    expected = commands.python_file(ROOT, 'tools/vm_artifacts.py', '--output', output, *VM_ARGS)
    assert planned == [expected] and not safety
    allocate = Mock(return_value=output)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'artifacts', args, pipe=False) == 0
    allocate.assert_called_once_with(output)
    assert execute.call_args.args[0] == expected
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    with pytest.raises(ValueError, match='artifact output must be a new'):
        commands.plan(ROOT, 'artifacts', args)


@pytest.mark.parametrize('declaration', ['named_input(fixture_source=choose())',
    'named_input(**options)', 'named_input("rpm")',
    'named_input()\nnamed_input(fixture_source=True)'])
def test_ambiguous_input_declaration_refuses_before_allocation(tmp_path, monkeypatch, declaration):
    wrapper = tmp_path / 'check_future.py'
    wrapper.write_text(declaration)
    monkeypatch.setattr(commands.host, 'confined_file', lambda root, path: str(wrapper))
    allocate = Mock()
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    with pytest.raises(ValueError, match='qualification'):
        commands.qualification_artifact_command(ROOT, 'system', ['check_future'])
    allocate.assert_not_called()


@pytest.mark.parametrize('upgrade', [False, True])
def test_fedora_refuses_wrong_cached_format_before_build(
        tmp_path, monkeypatch, upgrade):
    import vm_artifacts
    import build_test_artifacts
    configured = vm_artifacts.selected()
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: replace(configured,
        family='fedora44-x86_64', package_format='rpm'))
    candidate = tmp_path / 'existing'
    candidate.mkdir()
    preserved = candidate / 'preserved'
    preserved.write_bytes(b'existing DEB evidence')
    monkeypatch.setattr(vm_artifacts, 'check', Mock())
    verify = Mock(return_value={'artifacts': {'package': {'path': 'package.deb'}}})
    monkeypatch.setattr(build_test_artifacts, 'verify', verify)
    verify_upgrade = Mock(return_value={'packages': {'current': {'architecture': 'amd64'}}})
    monkeypatch.setattr(build_test_artifacts, 'verify_upgrade', verify_upgrade)
    control = Mock()
    control.run.return_value = 5
    assert vm_artifacts.prepare(ROOT, control, {}, candidate=candidate, output=candidate,
                                upgrade_inputs=upgrade) == 2
    assert control.run.call_count == 1
    assert preserved.read_bytes() == b'existing DEB evidence'
    assert verify.call_count == (0 if upgrade else 1)
    assert verify_upgrade.call_count == (1 if upgrade else 0)


@pytest.mark.parametrize('output', [
    '/etc/onpc-input', '/tmp/unrelated', '/tmp/onpc-input/nested',
    '/tmp/../tmp/onpc-input', 'onpc-input', '/tmp//onpc-input',
])
def test_named_artifact_build_refuses_unconfined_outputs(output):
    with pytest.raises(ValueError, match='artifact output'):
        commands.plan(ROOT, 'artifacts', ['build', '--output', output])


def test_named_artifact_build_refuses_existing_and_dangling_paths(monkeypatch):
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    with pytest.raises(ValueError, match='artifact output'):
        commands.plan(ROOT, 'artifacts', ['build', '--output', '/tmp/onpc-existing'])


@pytest.mark.parametrize('previous', ['missing', 'malformed', 'unfinished', 'marked',
                                      'oversized', 'peer-transfer', 'malformed-peer', 'busy'])
def test_named_artifact_allocation_is_exclusive_private_and_retained(tmp_path, monkeypatch, previous):
    import test_retention

    output = tmp_path / 'new-output'
    monkeypatch.setattr(commands, 'artifact_output', lambda _: str(output))
    store = test_retention.Store(tmp_path / 'retention-selected')
    if previous == 'busy':
        with store.session():
            with pytest.raises(test_retention.OwnerBusy):
                with store.execution_session():
                    pytest.fail('an active storage owner was bypassed')
            assert not output.exists()
        return
    if previous != 'missing':
        store.path.mkdir(mode=0o700)
        journal = store.path / 'current.json'
        journal.write_text('{' if previous == 'malformed' else json.dumps(
            dict(run='a' * 32, finished=False, paths=[], history=[])))
        journal.chmod(0o600)
        if previous == 'oversized':
            with journal.open('r+b') as stream:
                stream.truncate(8 * 1024 ** 2 + 1)
        if previous == 'marked':
            (store.path / 'recovery-required').touch(mode=0o600)
    peer_input = None
    if previous in ('peer-transfer', 'malformed-peer'):
        peer = tmp_path / 'retention-batch'
        peer.mkdir(mode=0o700)
        peer_input = tmp_path / 'old-input'
        peer_input.mkdir(mode=0o700)
        (peer_input / 'payload').write_text('preserve old transfer input')
        info = peer_input.stat()
        live = dict(path=str(peer_input), device=info.st_dev, inode=info.st_ino, mode=0o700)
        marker = peer / 'input-transfer.json'
        marker.write_text('{' if previous == 'malformed-peer' else json.dumps(dict(
            transaction='c' * 32, phase='pending', selector='check_existing', vm='selected',
            source=str(peer), destination=str(store.path), source_run='b' * 32,
            destination_run='a' * 32, live=live, stale=dict(live, inode=info.st_ino + 1))))
        marker.chmod(0o600)
    with store.execution_session():
        assert commands.allocate_artifact_output('/tmp/onpc-input') == str(output)
        assert output.stat().st_mode & 0o777 == 0o700
        (output / 'preserve').write_text('existing input')
        with pytest.raises(FileExistsError):
            commands.allocate_artifact_output('/tmp/onpc-input')
        assert (output / 'preserve').read_text() == 'existing input'
    assert str(output) in (store.path / 'current.json').read_text()
    if peer_input is not None:
        assert (peer_input / 'payload').read_text() == 'preserve old transfer input'
        assert marker.exists()


def test_named_artifact_build_detached_route_registers_before_builder(tmp_path, monkeypatch):
    import regression_process

    output = str(ROOT / 'output/test-runs/host/allocations/onpc-parent-setup-input')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=output)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(
        ROOT, 'artifacts', ['build', '--output', output], pipe=False) == 0
    allocate.assert_called_once_with(output)
    assert execute.call_args.args[0] == commands.python_file(
        ROOT, 'tools/build_test_artifacts.py', '--matrix', '--output', output)




@pytest.mark.parametrize('selector', ['check_e2e_parent_save',
    'check_e2e_operate_public_connectivity_controls',
    'check_e2e_operate_public_connectivity_controls.py'])
def test_toggle_qualification_reuses_existing_inputs_without_overwriting(
        monkeypatch, synthetic_package_identity, selector):
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    validate = Mock()
    monkeypatch.setattr(commands, 'artifact_path', validate)
    allocate = Mock(side_effect=AssertionError('existing inputs replaced'))
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    assert commands.qualification_artifact_command(
        ROOT, 'system', [selector]) == commands.python_file(
            ROOT, 'tools/vm_artifacts.py', '--candidate', str(named_input()),
            '--output', str(named_input()), *VM_ARGS)
    validate.assert_called_once_with(str(named_input()))


def test_retention_permission_failure_preserves_output_and_starts_fresh_execution(
        tmp_path, monkeypatch, capsys, vm_execution_branch):
    import regression
    import test_retention
    import vm_selection
    import host_compute

    import test_activity
    # This simulated worker owns no part of the enclosing launcher's live pool.
    for name in (host_compute.VARIABLE, host_compute.TOKENS):
        monkeypatch.delenv(name, raising=False)
    # Exercise the worker's output retirement directly. Public VM selections now
    # enter the queue coordinator, which needs a complete checkout inventory.
    monkeypatch.setenv(vm_selection.WORKER, '1')
    store = test_retention.Store(test_activity.retention_path(tmp_path))
    with pytest.raises(PermissionError):
        with store.session():
            scratch = tmp_path / 'sbuild-scratch'
            scratch.mkdir(mode=0o711)
            test_retention.retain(scratch, mode=0o711)
            private = scratch / 'private-chroot'
            private.mkdir(mode=0)
    journal = store.path / 'current.json'
    original = journal.read_bytes()
    monkeypatch.setattr(commands, '__file__', str(tmp_path / 'tools/test_commands.py'))
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression, 'retained_main', execute)
    try:
        assert commands._main(['all', *VM_ARGS]) == 0
        diagnostic = capsys.readouterr().err
        assert 'preserved unavailable historical output journal' in diagnostic
        assert 'Permission denied' in diagnostic or 'PermissionError' in diagnostic
        assert 'private-chroot' in diagnostic
        execute.assert_called_once()
        preserved = list(store.path.parent.glob(store.path.name + '-preserved-*'))
        assert len(preserved) == 1
        assert (preserved[0] / 'current.json').read_bytes() == original
        assert json.loads(journal.read_text())['paths'] == []
        assert private.exists()
    finally:
        private.chmod(0o700)


def test_internal_worker_uses_verified_activity_instead_of_attaching(tmp_path, monkeypatch):
    import regression_session
    import test_activity
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(commands, '__file__', str(tmp_path / 'tools/test_commands.py'))
    monkeypatch.setattr(commands, 'validate', Mock())
    attach = Mock(side_effect=AssertionError('worker attached to its own session'))
    monkeypatch.setattr(regression_session, 'main', attach)
    execute = Mock(return_value=7)
    monkeypatch.setattr(commands, '_main', execute)
    with test_activity.activity(tmp_path):
        assert commands.main(['static', 'shell']) == 7
    execute.assert_called_once_with(['static', 'shell'])


def test_detached_e2e_failed_build_never_starts_privileged_runner(tmp_path, monkeypatch):
    import regression_process
    monkeypatch.setattr(commands, 'plan', lambda *_: (
        [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner', 'e2e']], False))
    monkeypatch.setattr('tempfile.mkdtemp', lambda **_: str(tmp_path))
    execute = Mock(return_value=130)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'e2e', [], pipe=False) == 130
    execute.assert_called_once()
    assert execute.call_args.args[0][2].endswith('/tools/vm_artifacts.py')


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    import test_source
    # These inputs are a separate checkout, so they cannot borrow the outer
    # runner's source ownership. The outer descriptor remains with its owner.
    for key in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS):
        monkeypatch.delenv(key, raising=False)
    for category in ('unit', 'component', 'ui', 'child'):
        directory = tmp_path / 'tests' / category
        directory.mkdir(parents=True)
        (directory / 'test_future.py').touch()
    (tmp_path / 'tests/child/future.test.mjs').touch()
    (tmp_path / 'tests/child/future_test.js').touch()
    return tmp_path


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
def test_future_paths_expand_only_in_category(checkout, category):
    assert host.selection(checkout, [f'tests/{category}/test_*.py::test_case[x*y]'], category) == [
        f'tests/{category}/test_future.py::test_case[x*y]']
    for other in ('system', 'e2e', 'integration'):
        with pytest.raises(ValueError):
            host.selection(checkout, [f'tests/{other}/test_future.py'], category)


@pytest.mark.parametrize('option', ['-c=/tmp/evil', '-p=evil', '--rootdir=/tmp',
                                    '--override-ini=addopts=-p evil', '--pyargs',
                                    '--junitxml=/etc/file', '--ignore=/tmp', '--timeout=0'])
def test_rejects_pytest_bypasses(checkout, option):
    with pytest.raises(ValueError):
        host.pytest_command(checkout, ['tests/component', option], 'component')


def test_ui_globs_environment_timeout_and_exclusions(checkout):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    command = host.pytest_command(checkout, ['--timeout', '360s', 'tests/ui/test_*.py',
                                           '--ignore=tests/ui/test_future.py', '-q'], 'ui')
    assert command[:4] == [str(python), '-B', '-m', 'pytest']
    assert host.ui_timeout(['--timeout', '360s']) == 360
    assert '/usr/bin/timeout' not in command
    assert '-m=not live_e2e' in command
    assert '--ignore=tests/ui/test_future.py' in command
    assert command[-2:] == ['--', 'tests/ui/test_future.py']


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
@pytest.mark.parametrize('position', ['before', 'after', 'equals'])
def test_host_timeout_is_owned_by_runner_and_accepts_either_position(checkout, category, position):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    selected = [f'tests/{category}/test_future.py', '-q']
    options = (['--timeout', '180s', *selected] if position == 'before' else
               [*selected, '--timeout', '180s'] if position == 'after' else
               [*selected, '--timeout=180s'])

    command = host.pytest_command(checkout, options, category)

    assert host.pytest_timeout(options, category) == 180
    assert not any(value.startswith('--timeout') for value in command)
    assert command[-2:] == ['--', selected[0]]
    assert ('-m=not live_e2e' in command) is (category == 'ui')


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
@pytest.mark.parametrize('options', [
    ['--timeout'], ['--timeout=0'], ['--timeout', 'NaN'],
    ['--timeout', '1s', '--timeout=2s'], ['--timeout', '9' * 305 + 'd'],
])
def test_invalid_host_timeout_refuses_before_execution(checkout, category, options, monkeypatch):
    execute = Mock(side_effect=AssertionError('invalid timeout started a worker'))
    monkeypatch.setattr(host.subprocess, 'run', execute)
    with pytest.raises(ValueError):
        host.run_host(checkout, category, [f'tests/{category}', *options])
    execute.assert_not_called()


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
@pytest.mark.parametrize('detached', [False, True])
def test_host_execution_forwards_timeout_to_owned_controller(checkout, category, detached, monkeypatch):
    import regression_process
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    execute = Mock(return_value=124)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    monkeypatch.setattr(host, 'test_environment', lambda _: {})
    monkeypatch.chdir(checkout)
    run = regression_process.host_run if detached else host.run_host

    assert run(checkout, category, [f'tests/{category}', '--timeout=3m'],
               **({'pipe': False} if detached else {})) == 124

    assert execute.call_args.kwargs['timeout'] == 180
    assert execute.call_args.kwargs['kill_after'] == host.UI_KILL_AFTER
    assert not any(arg.startswith('--timeout') for arg in execute.call_args.args[0])


@pytest.mark.parametrize(('markers', 'expected'), [
    ([], '-m=not live_e2e'),
    (['-m', 'host_case'], '-m=(host_case) and not live_e2e'),
    (['-m', 'not live_e2e'], '-m=not live_e2e'),
    (['-m', 'live_e2e'], '-m=(live_e2e) and not live_e2e'),
])
def test_ui_launcher_always_excludes_vm_dependent_checks(checkout, markers, expected):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True, exist_ok=True)
    python.symlink_to('/usr/bin/python3')

    command = host.pytest_command(checkout, [*markers, 'tests/ui'], 'ui')

    assert expected in command


def test_untrusted_environment_is_removed(checkout, monkeypatch):
    for key in ('PYTHONPATH', 'PYTEST_PLUGINS', 'PYTEST_ADDOPTS', 'LD_PRELOAD',
                'MAKEFLAGS', 'MAKEFILES', 'NODE_OPTIONS', 'GJS_PATH', 'BASH_ENV', 'CC'):
        monkeypatch.setenv(key, '/tmp/untrusted')
    monkeypatch.setenv('SSH_AUTH_SOCK', '/caller/ssh-agent')
    env = host.environment(checkout)
    assert '/tmp/untrusted' not in env.values()
    assert env['PATH'] == '/usr/sbin:/usr/bin:/sbin:/bin'
    assert env['SSH_AUTH_SOCK'] == '/caller/ssh-agent'
    assert 'SSH_AUTH_SOCK' not in host.test_environment(checkout)
    from host_dispatch import ssh_environment
    assert ssh_environment(host.test_environment(checkout))['SSH_AUTH_SOCK'] == '/caller/ssh-agent'


@pytest.mark.parametrize('old', ['clean', 'staging', 'reclaiming', 'malformed', 'replaced', 'active', 'symlink'])
def test_pytest_storage_does_not_inherit_ramdisk_or_caller_override(checkout, monkeypatch, old, request):
    import test_storage
    parent = checkout / 'scratch'
    parent.mkdir(mode=0o700)
    original_directory = test_storage.directory
    monkeypatch.setattr(test_storage, 'directory', lambda kind, **kwargs:
                        parent if kind == 'scratch' else original_directory(kind, **kwargs))
    monkeypatch.setattr(test_storage, '_scratch', None)
    monkeypatch.setattr(test_storage, '_scratch_fd', None)
    callbacks = []
    monkeypatch.setattr(test_storage.atexit, 'register', lambda action, *args: callbacks.append((action, args)))
    old_path, old_owner = None, None
    def close_owned():
        nonlocal old_owner
        if old_owner is not None:
            os.close(old_owner)
            old_owner = None
        while callbacks:
            action, args = callbacks.pop()
            action(*args)
    request.addfinalizer(close_owned)
    if old in ('staging', 'reclaiming'):
        (parent / ('initializing.json' if old == 'staging' else 'reclaiming.json')).write_text('{')
        if old == 'staging':
            old_path = parent / 'initializing'
            old_path.mkdir(mode=0o700)
    elif old != 'clean':
        old_path = parent / ('run-' + 'a' * 32)
        if old == 'symlink':
            target = checkout / 'unrelated'
            target.mkdir(mode=0o700)
            old_path.symlink_to(target, target_is_directory=True)
        else:
            old_path.mkdir(mode=0o700)
            old_owner = os.open(old_path / 'owner', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            if old == 'active':
                fcntl.flock(old_owner, fcntl.LOCK_EX)
            info = old_path.stat()
            receipt = old_path / 'identity.json'
            receipt.write_text('{' if old == 'malformed' else json.dumps(dict(
                path=str(old_path), device=info.st_dev,
                inode=info.st_ino + int(old == 'replaced'), mode=0o700)))
            receipt.chmod(0o600)
    if old_path is not None:
        (old_path / 'payload').write_text('preserve old or foreign payload')
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        monkeypatch.setenv(key, '/tmp/untrusted')
    env = host.test_environment(checkout)
    from pathlib import Path
    assert Path(env['TMPDIR']).is_relative_to(parent)
    assert old_path is None or not Path(env['TMPDIR']).is_relative_to(old_path)
    assert 'TMP' not in env and 'TEMP' not in env
    probe = checkout / 'storage_probe.py'
    probe.write_text('''import os, pathlib, tempfile
with tempfile.TemporaryDirectory(prefix='onpc-storage-probe-') as directory:
    assert pathlib.Path(directory).parent == pathlib.Path(os.environ['TMPDIR'])
    with tempfile.TemporaryFile() as capture:
        assert os.readlink('/proc/self/fd/' + str(capture.fileno())).startswith(os.environ['TMPDIR'] + '/')
        capture.write(b'captured output')
        capture.seek(0)
        assert capture.read() == b'captured output'
''')
    try:
        subprocess.run([sys.executable, '-B', str(probe)], env=env, check=True, timeout=10)
        assert host.environment(checkout)['TMPDIR'] == env['TMPDIR']
        if old_path is not None:
            assert (old_path / 'payload').read_text() == 'preserve old or foreign payload'
        if old in ('staging', 'reclaiming'):
            marker = parent / ('initializing.json' if old == 'staging' else 'reclaiming.json')
            assert marker.read_text() == '{'
    finally:
        close_owned()


def test_component_runs_only_selected_tests_without_prerequisite_suite(checkout, monkeypatch):
    prerequisite = Mock(side_effect=ValueError('failed prerequisites'))
    execute = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(host, 'prerequisites', prerequisite)
    monkeypatch.setattr(host.subprocess, 'run', execute)
    monkeypatch.chdir(checkout)
    assert host.run_host(checkout, 'component', []) == 0
    prerequisite.assert_not_called()
    execute.assert_called_once()


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
def test_collect_only_never_starts_cleanup(checkout, monkeypatch, category):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    prerequisite = Mock()
    execute = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(host, 'prerequisites', prerequisite)
    monkeypatch.setattr(host.subprocess, 'run', execute)
    if category == 'ui':
        import regression_process
        monkeypatch.setattr(regression_process.Control, 'run',
                            lambda *args, **kwargs: execute().returncode)
    monkeypatch.chdir(checkout)
    host.run_host(checkout, category, ['--collect-only'])
    prerequisite.assert_not_called()
    execute.assert_called_once()


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
def test_scheduled_collection_keeps_inventory_protocol_without_execution_ownership(
        checkout, monkeypatch, category):
    from contextlib import contextmanager
    import regression_process
    import test_activity
    @contextmanager
    def installed(controller, *, pipe=True):
        assert pipe is True
        yield controller
    monkeypatch.setattr(regression_process.Control, 'installed', installed)
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    monkeypatch.setattr(host, '__file__', str(checkout / 'tools/test_launcher.py'))
    monkeypatch.setattr(host, 'prerequisites', Mock(side_effect=AssertionError('collection cleanup')))
    monkeypatch.setattr(test_activity, 'activity', Mock(side_effect=AssertionError('execution owner')))
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert host.main(['--unattended', '--collect-only', '--timeout', '180s',
                      f'tests/{category}/test_future.py'], category=category) == 0
    command = execute.call_args.args[0]
    env = execute.call_args.kwargs['env']
    assert env['ONPC_REGRESSION_EVENTS'] == env['ONPC_REGRESSION_INVENTORY'] == '1'
    assert '--collect-only' in command and command[-1] == f'tests/{category}/test_future.py'
    assert execute.call_args.kwargs['timeout'] == 180
    execute.assert_called_once()


@pytest.mark.parametrize('category,argv', [
    ('check', ['-f', '/tmp/evil']), ('check', ['SHELL=/tmp/evil']),
    ('all', ['--component=unit']), ('fast', ['--component=$(touch /tmp/no)']),
    ('fast', ['--type', 'a;id']), ('child-node', ['--eval=process.exit()']),
    ('child-gjs', ['tests/child/future.test.mjs']), ('static', ['/tmp/check.py']),
    ('traceability', ['--manifest=/tmp/input']), ('coverage', ['--cov=/tmp']),
    ('artifacts', ['build', '/etc/target']), ('fixtures', ['--output=/tmp/evil']),
    ('integration', []), ('graphical-worker', ['--vm', vm_name()]),
    ('package-notice', ['--list']),
])
def test_category_option_injection_rejected(checkout, category, argv):
    with pytest.raises(ValueError):
        commands.plan(checkout, category, argv)


def test_e2e_listing_is_host_safe_and_pending_execution_refused(monkeypatch, tmp_path):
    plan, safety = commands.plan(ROOT, 'e2e', ['--list'])
    assert 'pkexec' not in plan[0][0]
    assert plan[0][2].endswith('/tests/e2e/runner.py')
    assert '--list' in plan[0]
    assert safety is False
    # Listing loads the shared password module without reading credentials.
    # Supply the unrelated execution prerequisite without using the host .envrc.
    import test_account_password
    password = Mock(return_value='fixture-password')
    monkeypatch.setattr(test_account_password, 'read_password', password)
    # Keep this refusal check independent of real scenarios becoming ready.
    inventory_path = ROOT / 'tests/e2e/scenarios.json'
    document = json.loads(inventory_path.read_bytes())
    variant = next(variant for scenario in document['scenarios']
                   for variant in scenario['variants'] if variant['coverage_id'] == 66)
    variant.update(status='pending', pending_reason='Controlled pending selection', executable=None)
    inventory_bytes = json.dumps(document).encode()
    read_bytes = type(ROOT).read_bytes

    def read_inventory(path):
        if path == inventory_path:
            return inventory_bytes
        return read_bytes(path)

    monkeypatch.setattr(type(ROOT), 'read_bytes', read_inventory)
    with pytest.raises(ValueError, match='selection:pending'):
        commands.plan(ROOT, 'e2e', ['--id=66', '--artifacts=/tmp/onpc-future'])
    password.assert_called_once_with()

    heavy, _ = commands.plan(ROOT, 'e2e', ['--list', '--subcategory', 'e2e-heavy'])
    assert '--subcategory' in heavy[0]
    assert commands.selections(ROOT, ['e2e-general', '--list']) == [
        ('e2e', ['--subcategory', 'general', '--list'])]
    assert commands.repair_inventory(ROOT, ['e2e-general'])['e2e']['args'] == [
        '--subcategory', 'general']
    for request in (['e2e-general', 'e2e'], ['e2e', 'e2e-general'],
                    ['e2e-heavy', 'e2e-general']):
        assert commands.selections(ROOT, request) == [('e2e', [])]
        assert commands.repair_inventory(ROOT, request)['e2e']['args'] == []
        assert not commands.host_only_request(request)
    assert not commands.host_only_request(['unit', '-q', 'e2e-general'])
    assert not commands.host_only_request(['host', 'e2e-general'])
    assert commands.includes_host_request(ROOT, ['host', 'e2e-general'])
    preflight = runpy.run_path(str(ROOT / 'tests/e2e/runner.py'))['preflight']
    listed = preflight(['--list', '--subcategory', 'e2e-heavy'], root=ROOT)
    assert [case['coverage_id'] for case in listed['cases']] == [253]
    assert all('vm_tags' not in case for case in listed['cases'])

    import fix_tests
    import launcher_controller
    from vm_selection import VARIABLE, vm_config

    targets = [vm_config.load(vm_name(index), local=False) for index in (0, 1)]
    selector = ','.join(vm.id for vm in targets)
    request = ['e2e', '--id', '22,30', '--vm', selector]
    monkeypatch.setattr(sys, 'argv', ['tools/fix-tests', *request])
    monkeypatch.delenv(VARIABLE)

    def start(root, kind, command, *, on_start, **kwargs):
        assert kind == 'fix-tests'
        command(tmp_path, 0)
        on_start(tmp_path)
        return tmp_path, True

    monkeypatch.setattr(fix_tests.launcher, 'select', start)
    monkeypatch.setattr(fix_tests.launcher, 'report_start', lambda *args, **kwargs: 0)
    assert launcher_controller._entry(ROOT, 'fix-tests', None, request, fix_tests.main) == 0
    assert json.loads((tmp_path / 'vm.json').read_text())['vm']['vms'] == [vm.name for vm in targets]
    saved = json.loads((tmp_path / 'request.json').read_text())
    assert saved['categories'] == request[:3] and saved['vm'] == selector

    qualified = preflight(['--qualify-lunar-profile'], root=ROOT, allow_missing_artifacts=True)
    assert qualified == {'mode': 'lunar-profile-qualification', 'subcategory': 'e2e-heavy'}
    launch_quit, tray_alias = '--qualify-lunar-launch-quit', '--qualify-lunar-tray'
    for option in (launch_quit, tray_alias):
        assert preflight([option], root=ROOT, allow_missing_artifacts=True) == {
            'mode': 'lunar-launch-quit-qualification', 'subcategory': 'e2e-heavy'}
        assert commands.fixture_execution_target('e2e', [option]) is None
    assert commands.selections(ROOT, ['e2e', tray_alias, 'e2e', launch_quit]) == [('e2e', [launch_quit])]
    assert commands.selections(ROOT, ['e2e', tray_alias, launch_quit]) == [('e2e', [launch_quit])]
    assert preflight(['--qualify-lunar-autostart'], root=ROOT, allow_missing_artifacts=True) == {
        'mode': 'lunar-autostart-qualification', 'subcategory': 'e2e-heavy'}
    assert commands.fixture_execution_target('e2e', ['--qualify-lunar-autostart']) is None
    assert preflight(['--qualify-minecraft-entry-exit'], root=ROOT, allow_missing_artifacts=True) == {
        'mode': 'minecraft-entry-exit-qualification', 'subcategory': 'e2e-heavy'}
    assert commands.fixture_execution_target('e2e', ['--qualify-minecraft-entry-exit']) is None
    assert preflight(['--qualify-lunar-denial'], root=ROOT, allow_missing_artifacts=True) == {
        'mode': 'lunar-denial-qualification', 'subcategory': 'e2e-heavy'}
    assert preflight(['--qualify-lunar-login-denial'], root=ROOT, allow_missing_artifacts=True) == {
        'mode': 'lunar-login-denial-qualification', 'subcategory': 'e2e-heavy'}
    assert preflight(['--qualify-minecraft-access'], root=ROOT, allow_missing_artifacts=True) == {
        'mode': 'minecraft-access-qualification', 'subcategory': 'e2e-heavy'}
    from vm_recording import case_identity
    assert case_identity(ROOT, 'e2e', {'nodeid': '--qualify-lunar-login-denial'}) == (
        'check_e2e_lunar_login_denial', 'Check blocked Lunar access after sign-in')
    assert case_identity(ROOT, 'e2e', {'nodeid': '--qualify-lunar-autostart'}) == (
        'check_e2e_lunar_autostart', 'Check allowed Lunar startup after sign-in')
    assert case_identity(ROOT, 'e2e', {'nodeid': '--qualify-minecraft-entry-exit'}) == (
        'check_e2e_minecraft_entry_exit', 'Open and close the Minecraft launcher')
    assert case_identity(ROOT, 'e2e', {'nodeid': '--qualify-lunar-launch-quit'}) == (
        'check_e2e_lunar_launch_quit', 'Launch and stop Lunar by command')
    assert case_identity(ROOT, 'e2e', {'nodeid': '--qualify-lunar-denial'}) == (
        'check_e2e_lunar_denial', 'Observe Lunar command denial')
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    resolved = dispatcher['selection'](ROOT, ['e2e', tray_alias, *VM_ARGS], allow_missing_artifacts=True)
    assert launch_quit in resolved and tray_alias not in resolved
    assert '--qualify-lunar-login-denial' in dispatcher['selection'](
        ROOT, ['e2e', '--qualify-lunar-login-denial', *VM_ARGS], allow_missing_artifacts=True)
    assert '--qualify-lunar-autostart' in dispatcher['selection'](
        ROOT, ['e2e', '--qualify-lunar-autostart', *VM_ARGS], allow_missing_artifacts=True)
    assert '--qualify-minecraft-access' in dispatcher['selection'](
        ROOT, ['e2e', '--qualify-minecraft-access', *VM_ARGS], allow_missing_artifacts=True)
    assert '--qualify-minecraft-entry-exit' in dispatcher['selection'](
        ROOT, ['e2e', '--qualify-minecraft-entry-exit', *VM_ARGS], allow_missing_artifacts=True)
    assert '--qualify-lunar-denial' in dispatcher['selection'](
        ROOT, ['e2e', '--qualify-lunar-denial', *VM_ARGS], allow_missing_artifacts=True)
    with pytest.raises(ValueError, match='requires-heavy-subcategory'):
        preflight(['--qualify-lunar-profile', '--subcategory', 'general'],
                  root=ROOT, allow_missing_artifacts=True)
    with pytest.raises(ValueError, match='cannot-select-scenarios'):
        preflight(['--qualify-lunar-profile', '--id', '253'], root=ROOT,
                  allow_missing_artifacts=True)


def test_privileged_parent_symlink_is_rejected(checkout):
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    external = checkout / 'outside'
    external.mkdir()
    (external / 'check_future.py').touch()
    (checkout / 'tests/integration').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError):
        dispatcher['selection'](checkout, ['system', 'check_future'])


def test_system_listing_is_host_safe_and_lists_only_registered_tests():
    plan, safety = commands.plan(ROOT, 'system', ['--list'])
    assert all('pkexec' not in command[0] for command in plan)
    assert len(plan) == 2
    assert plan[0][2] == str(ROOT / 'tests/integration/system_runner.py')
    assert '--list' in plan[0]
    assert plan[1] == ['/usr/bin/python3', '-B',
                       str(ROOT / 'tests/integration/system_checks.py')]
    assert safety is False
    listing = runpy.run_path(str(ROOT / 'tests/integration/system_checks.py'))
    registered = {item['name'] for item in listing['inventory']()}
    assert registered == set(listing['SYSTEM_CHECKS'])
    assert len(registered) == 23
    scheduled = listing['runnable']()
    assert scheduled and len(scheduled) == len(set(scheduled))
    assert set(scheduled).isdisjoint({
        'check_test_recovery', 'check_graphical_recovery', 'check_system_recovery',
        'check_tmp_storage', 'check_tmp_storage_cleanup', 'check_storage_migration',
        'check_retained_runs_cleanup'})
    assert {'check_fixture_snapshots', 'check_fixture_live_refresh',
            'check_fixture_system_installed', 'check_graphical_attachment',
            'check_graphical_smoke', 'check_graphical_transport',
            'check_graphical_serial', 'check_e2e_watch',
            'check_e2e_upgrade_assets',
            'check_e2e_give_repeated_public_operations_distinct_stages'
            }.isdisjoint(scheduled)
    assert {'check_e2e_panel_language_refresh', 'check_e2e_overlay_translated_approval',
            'check_e2e_baseline_journey', 'check_e2e_natural_expiry',
            'check_e2e_parent_save', 'check_e2e_kiosk_update_reentry'}.isdisjoint(registered)
    assert {'check_e2e_auth_prompt', 'check_e2e_kiosk_feedback_confinement',
            'check_e2e_kiosk_configuration_recovery', 'check_fixture_e2e_installed',
            'check_graphical_credentials'} <= set(scheduled)
    assert listing['HOST_CHECKS'] == {
        'graphical-worker': 'check_graphical_worker', 'package-notice': 'check_package_notice'}
    assert set(listing['HOST_CHECKS'].values()).isdisjoint(registered)
    assert all(commands.CATEGORIES[category].scope == 'host'
               for category in listing['HOST_CHECKS'])
    ubuntu = set(listing['runnable'](host_os='ubuntu'))
    fedora = set(listing['runnable'](host_os='fedora'))
    assert ubuntu == fedora == set(scheduled)
    assert commands.execution_selections(ROOT, [('system', [])]) == [
        ('system', []), ('system', ['--id', '287', '--upgrade-inputs']),
        ('system', ['--id', '288', '--upgrade-inputs']),
        *(('system', [name]) for name in scheduled)]
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    with pytest.raises(ValueError, match='check-selector-conflict'):
        dispatcher['selection'](ROOT, ['system', '--list', 'check_fixture_snapshots'])


def test_host_aggregate_dispatch_and_invalid_arguments(monkeypatch):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main(['host']) == 7
    execute.assert_called_once_with(ROOT, phases=('host',))
    execute.reset_mock()
    for args in (['--skip-backing-verification'], ['--component=ui'], ['--unattended']):
        assert commands._main(['host', *args]) == 2
    execute.assert_not_called()


@pytest.mark.parametrize('serial', [False, True])
def test_host_build_qualification_is_fixed_and_never_dispatches_vm(monkeypatch, serial):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    args = ['--serial-builds'] if serial else []
    assert commands._main(['host-builds', *args]) == 7
    execute.assert_called_once_with(ROOT, phases=('host',), serial_builds=serial)
    execute.reset_mock()
    for extra in (['--serial'], ['--serial-builds', '--serial-builds'], ['--area', 'session'],
                  ['--skip-backing-verification'], ['--command=id']):
        assert commands._main(['host-builds', *extra]) == 2
    execute.assert_not_called()
