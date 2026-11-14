"""Boundary and execution tests for all approved test category routes."""
from tools.test_storage import named_input
from tests.support.vm_registry import vm_name
from dataclasses import replace
from contextlib import nullcontext
import fcntl
import json
import os
import runpy
import subprocess
import sys
from unittest.mock import Mock
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
        assignment = shared.claim('deb', 'one', work, vm_test_queue.source_identity(tmp_path))
        request = tmp_path / 'work.json'
        request.write_text(json.dumps(dict(selection=['system', 'check_snapshot'],
            passed={'system': []}, assignment=assignment, recovering=False)))
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
        saved = test_checkpoint.Checkpoint(tmp_path, selection, resume=True, binding='one')
        evidence = saved.state['queue_evidence']
        assert evidence['source'] == assignment['source'] != vm_test_queue.source_identity(tmp_path)
        assert shared.accept(assignment, evidence, 0)
        assert source.read_text() == 'incoming change'
        shared.retry('deb', 'check_snapshot')
        assignment = shared.claim('deb', 'one', work, vm_test_queue.source_identity(tmp_path))
        request.write_text(json.dumps(dict(selection=['system', 'check_snapshot'],
            passed={'system': []}, assignment=assignment, recovering=False)))
        monkeypatch.setenv(vm_test_queue.FAMILY_WORK, str(request))
        monkeypatch.setattr(vm_test_queue, 'reservation', lambda *args, **kwargs: nullcontext())
        recoveries = []
        monkeypatch.setattr(test_recovery, 'cleanup',
                            lambda root: recoveries.append(control.stopped.is_set()) or 0)
        monkeypatch.setattr(commands, '_main', lambda *args, **kwargs: pytest.fail('cancelled test started'))
        control.stopped.set()
        assert vm_test_queue.worker(['--execute', 'one', 'system', 'check_snapshot']) == 130
        saved = test_checkpoint.Checkpoint(tmp_path, selection, resume=True, binding='one')
        evidence = saved.state['queue_evidence']
        assert recoveries == [False] and evidence['cleanup'] and evidence['interrupted']
        assert evidence['assignment'] == assignment['assignment'] and not evidence['passed']
        assert not shared.accept(assignment, evidence, 130, interrupted=True)
        shared.recover(assignment, cleanup=True)
        assert shared.pending('deb') == [work]


def test_impact_triage_stays_read_only_and_bounded(tmp_path, monkeypatch):
    import agent_adapter
    import agent_claude
    import agent_codex
    import detached_launcher
    import fix_tests

    # Exercise the request boundary without a model session or native CLI.
    prepared = []
    monkeypatch.setattr(detached_launcher, 'prepare_session',
                        lambda request, environment: prepared.append(request) or request)
    selection = agent_adapter.AgentSelection('codex', tmp_path)
    request = fix_tests.impact_command(tmp_path, tmp_path, selection=selection)
    assert request.permissions == 'read_only'
    assert not request.delegation.enabled and request.delegation.roles == ()
    assert request.logical_tier == 'high'
    assert (request.model, request.effort) == ('gpt-6.1-sol', 'high')
    assert request.standard_speed and request.selection == selection
    assert json.loads(request.schema.read_text())['properties']['impact']['enum'] == ['yes', 'no', 'unsure']
    for adapter, model in ((agent_codex.CodexAdapter(), 'gpt-6.1-sol'),
                           (agent_claude.ClaudeAdapter(), 'claude-opus-5-5')):
        assert adapter.resolve_profile('impact_triage') == (model, 'high')
        with pytest.raises(ValueError, match='impact triage'):
            adapter.resolve_profile('impact_triage', effort='low')
    with pytest.raises(ValueError, match='not qualified'):
        fix_tests.impact_command(tmp_path, selection=agent_adapter.AgentSelection('claude', tmp_path))
    assert len(prepared) == 1

    # Native supervision receives an agent operation (including capacity
    # recovery), while low unit-repair defaults cannot change triage's profile.
    import launcher_chat
    calls = []
    monkeypatch.setattr(detached_launcher, 'prepare_session', lambda request, environment:
                        SimpleNamespace(request=request, adapter=SimpleNamespace(name='codex')))
    monkeypatch.setattr(detached_launcher, 'supervise',
                        lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
    monkeypatch.setattr(launcher_chat, 'read_state', lambda _: {'task_id': 'unit'})
    monkeypatch.setattr(fix_tests, 'record_usage', lambda *args, **kwargs: None)
    (tmp_path / 'checkpoint.json').write_text(json.dumps({'agent_selection': selection.record()}))
    metadata = dict(failure={'category': 'unit', 'case': 'case', 'vm': ''}, repair_session=1)
    assert fix_tests.supervise(tmp_path, tmp_path, 0, 'impact-triage', 'impact triage',
                               'gpt-6.1-sol', 'low', json.dumps(metadata)) == 0
    args, kwargs = calls[0]
    assert args[3] == 'agent' and kwargs['interactive']
    assert (args[4].request.model, args[4].request.effort) == ('gpt-6.1-sol', 'high')
    assert args[4].request.permissions == 'read_only'

    ticket = dict(id='1' * 32, attempt='2' * 32, source={'digest': 'a' * 64, 'generation': 0},
                  selection=[['unit', []]], work={'category': 'unit'}, case='case', vm='')
    evidence = dict(output_tail='failed operation', limit_reached=True,
                    files=[dict(source='log', tail='é' * 10000)] * 12,
                    read_failures=[dict(source='other', error='PermissionError')])
    failure = dict(prompt='failure', operation='setup', expected='ready', actual='failed')
    context, digest = fix_tests.impact_context(ticket, failure, evidence=evidence,
                                              shared_inputs={'fixture': 'current'})
    assert len(context['logs']) == 8 and context['evidence_limits']['omitted_files'] == 4
    assert context['logs'][0]['tail']['truncated']
    assert len(context['logs'][0]['tail']['text'].encode('utf-8')) <= 8192
    assert context['output']['text'] == 'failed operation'
    assert context['evidence_limits']['failures']['value'] == evidence['read_failures']
    assert digest != fix_tests.impact_context(ticket, dict(failure, actual='changed'),
                                             evidence=evidence, shared_inputs={'fixture': 'current'})[1]
    assert fix_tests.impact_context(ticket, failure)[0]['evidence_limits']['unavailable']


def test_impact_triage_reuses_only_current_evidence_without_spending_again(tmp_path, monkeypatch):
    import fix_tests
    import vm_test_queue

    source = dict(digest='a' * 64, generation=0)
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda _: dict(source))
    monkeypatch.setattr(fix_tests, 'resolve_selection', lambda _: 'qualified')
    monkeypatch.setattr(fix_tests, 'impact_command', lambda *args, **kwargs:
                        SimpleNamespace(request=SimpleNamespace(model='native-high', effort='high')))
    ticket = dict(id='1' * 32, transaction='2' * 32, attempt='3' * 32, source=dict(source),
                  selection=[['_host', ['unit']]], work={'category': 'unit'}, case='case', vm='')
    decision = dict(impact='no', reason='Only the private input is affected.',
                    scope=['private input'], evidence=['The independent input is unchanged.'],
                    classification='test_issue')
    calls = []
    charges = []
    def charge(value):
        charges.append(value['id'])
        return len(charges)
    def session(kind, phase, metadata, **options):
        calls.append((kind, metadata, options))
        (tmp_path / 'agent-result.json').write_text(json.dumps(decision))
        return 0
    def triage(value):
        return fix_tests.triage_failure(tmp_path, tmp_path, value, {'error': 'failed input'},
                                        session=session, charge=charge)

    envelope = triage(ticket)
    assert envelope['decision'] == decision
    assert calls[0][0] == 'impact-triage'
    assert calls[0][1]['repair_session'] == 1
    assert calls[0][2] == dict(agent_model='native-high', agent_effort='high')
    ticket['impact'] = dict(envelope, ticket=ticket['id'], attempt=ticket['attempt'])
    assert triage(ticket) == envelope
    assert len(charges) == 1
    source.update(digest='b' * 64, generation=1)
    decision = dict(decision, impact='unsure')
    refreshed = triage(ticket)
    assert refreshed['source'] == source
    assert refreshed['evidence_digest'] != envelope['evidence_digest']
    assert refreshed['decision']['impact'] == 'unsure'
    assert len(charges) == 2
    decision = {'impact': 'no'}  # A missing scoped witness never opens admission.
    assert triage(ticket)['decision']['impact'] == 'unsure'


@pytest.fixture
def _controlled_public_repair(tmp_path, monkeypatch, isolated_source):
    import fix_tests
    import fix_tests_git
    import launcher_git
    import launcher_worktrees
    import test_source
    import vm_test_queue
    from launcher_runtime import TaskBudget
    from vm_selection import vm_config
    branch = vm_config.current_branch()
    monkeypatch.setattr(vm_config, 'current_branch', lambda: branch)

    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').touch()
    TaskBudget(run).initialize(None)
    from agent_adapter import AgentSelection
    selection = AgentSelection('codex', tmp_path)
    dependency = tmp_path / 'validation-input.py'
    dependency.write_text('original')
    control = SimpleNamespace(run=run, order=[], ticket=None,
        response=dict(status='test_fixed', summary='Corrected the private input.',
                      stage_paths=[dependency.name], verification_case='exact', blocker=None))
    def snapshot(_):
        return ({dependency.name: launcher_git.worktree_fingerprint(dependency)}
                if dependency.read_text() != 'original' else {})
    monkeypatch.setattr(fix_tests, 'requested_inventory', lambda *args, **kwargs:
                        {'unit': {'args': ['original-selector']}})
    monkeypatch.setattr(fix_tests, 'resolve_selection', lambda _: selection)
    monkeypatch.setattr(launcher_worktrees, 'pull_at_boundary', lambda *args: None)
    monkeypatch.setattr(launcher_git, 'worktree_snapshot', snapshot)
    monkeypatch.setattr(fix_tests_git, 'worktree_snapshot', snapshot)
    monkeypatch.setattr(launcher_git, 'git_output', lambda *args: SimpleNamespace(stdout='same-head'))
    monkeypatch.setattr(fix_tests_git, 'git_output', lambda *args: SimpleNamespace(stdout=''))
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda _: dict(
        digest=('a' if dependency.read_text() == 'original' else 'b') * 64,
        generation=isolated_source.generation()))
    monkeypatch.setattr(fix_tests, 'record_usage', lambda *args, **kwargs: None)
    order = control.order
    ticket = dict(id='a' * 32, transaction='b' * 32, attempt='c' * 32,
                  work=dict(category='unit', options=['original-selector'], cases=['exact'],
                            case='exact', area=False), case='exact', vm='',
                  impact=dict(decision=dict(classification='test_issue', reason='Only this test input.')))
    control.ticket = ticket
    def triage(root, directory, value, result, *, session, charge):
        assert charge(value) == 1
        order.append('triage')
        return dict(decision=ticket['impact']['decision'])
    monkeypatch.setattr(fix_tests, 'triage_failure', triage)
    class Agent:
        def __init__(self, command, **kwargs):
            assert 'agent' in command
            order.append('repair')
            dependency.write_text('changed validation dependency')
            (run / 'agent-result.json').write_text(json.dumps(control.response))
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def wait(self):
            return 0
    monkeypatch.setattr(fix_tests.subprocess, 'Popen', Agent)
    def closeout(self):
        order.append('closeout')
        assert self.state['repairs'][self.state['pending']]['coordinator_attempt']['accepted']
        self.state['repairs'].pop(self.state.pop('pending'))
        self.save()
    monkeypatch.setattr(fix_tests_git.RepairCommits, 'finish_pending', closeout)
    control.gate = test_source.RepairGate(run, root=tmp_path)
    control.worker = lambda **options: fix_tests.reserved_worker(
        tmp_path, run, 0, 'gpt-6.1-sol', '', '', requested='["unit"]',
        repair_gate=control.gate, **options)
    control.saved = lambda: json.loads((run / 'checkpoint.json').read_text())
    try:
        yield control
    finally:
        control.gate.release()


def test_public_repair_composes_triage_verification_and_closeout(
        tmp_path, monkeypatch, isolated_source, _controlled_public_repair):
    import base64
    import fix_tests
    import test_source
    import vm_test_queue
    from launcher_runtime import TaskBudget

    control = _controlled_public_repair
    run, order, ticket = control.run, control.order, control.ticket
    resumed = False
    class Execution:
        drained = True
        failure = None
        def refresh_impact(self):
            pass  # This fixture's impact is already current.
        def attempt(self, purpose, target=None):
            order.append(purpose)
            assert test_source.environment().get(test_source.WRITER) == str(run)
            assert purpose == 'recheck' or target == 'exact'
            accepted = purpose == 'verification'
            return dict(status=0 if accepted else 1, accepted=accepted,
                        reference=dict(source=vm_test_queue.source_identity(tmp_path), accepted=accepted))
    def execute(root, args, *, actions, **kwargs):
        assert args == (['--resume'] if resumed else []) + ['unit', 'original-selector']
        assert actions['admit_task']('unit')
        if not resumed:
            actions['triage'](ticket, {})
        result = actions['repair'](ticket, Execution())
        assert result['outcome'] == 'resolved' and result['attempt']['accepted']
        assert isolated_source.owner() is None
        actions['settle_task']('unit')
        return dict(status=0)
    monkeypatch.setattr(vm_test_queue, 'run', execute)
    with pytest.raises(fix_tests.ControllerReload):
        control.worker()
    saved = control.saved()
    key = '["unit", "exact", ""]'
    raw = saved['repairs'][key]['pending_response']
    assert json.loads(base64.b64decode(raw['response'])) == control.response
    assert isolated_source.owner() == str(run)
    assert isolated_source.generation() == 1
    assert order == ['triage', 'recheck', 'repair']

    # Interpreter replacement retains the writer but must apply the new code's
    # validators to the exact response before an attempt or Git close-out.
    resumed = True
    monkeypatch.setattr(test_source, '_generations', {})
    (run / 'agent-result.json').write_text('{}')
    validate = fix_tests.validate_result
    def current_validate(value):
        assert value == control.response
        assert control.saved()['session_counts'] == {key: 2}
        order.append('current validation')
        validate(value)
    monkeypatch.setattr(fix_tests, 'validate_result', current_validate)
    assert control.worker(reloading=True) == 0
    assert order == ['triage', 'recheck', 'repair', 'current validation', 'verification', 'closeout']
    saved = control.saved()
    assert saved['session_counts'] == {'["unit", "exact", ""]': 2}
    assert TaskBudget(run).read()['completed'] == 1

    # Git completion and coordinator settlement are separate transactions.
    # Recovery must use their exact shared attempt, without another execution.
    import fix_tests_git
    commits = fix_tests_git.RepairCommits(tmp_path, run)
    reference = dict(ticket=ticket['id'], attempt='d' * 32, purpose='verification',
                     source=vm_test_queue.source_identity(tmp_path), accepted=True, status=0)
    ticket['attempts'] = [reference]
    commits.state['closed_repair'] = dict(failure=['unit', 'exact', ''], attempt=reference)
    commits.state['rounds']['done'] = False
    commits.save()
    recovered = []
    def settle(root, args, *, actions, **kwargs):
        outcome = actions['repair'](ticket, Execution())
        recovered.append(outcome['attempt'])
        assert outcome['outcome'] == 'resolved'
        return dict(status=0)
    monkeypatch.setattr(vm_test_queue, 'run', settle)
    before = list(order)
    assert control.worker(reloading=True) == 0
    assert recovered == [reference]
    assert order == before
    # A different ticket/attempt cannot inherit that accepted result.
    assert commits.closed_attempt(dict(ticket, attempts=[])) is None

    # Legacy recovery additionally needs the completed controller commit and
    # its explicit journal link to this accepted attempt and source digest.
    commits.state.pop('closed_repair')
    commits.state['last_commit'] = 'e' * 40
    ticket['vm'] = 'original-vm'
    journal = run / 'commit-skill' / ('f' * 32)
    journal.mkdir(parents=True)
    receipt = dict(status='complete', source_commit='e' * 40, pushed_head='e' * 40,
        commit_message='TA: Fixed unit exact on original-vm', source=dict(path=str(tmp_path)),
        ownership=dict(accepted_attempt=reference['attempt'],
                       accepted_source_digest=reference['source']['digest']))
    (journal / 'progress.json').write_text(json.dumps(receipt))
    monkeypatch.setattr(fix_tests_git, 'git_output', lambda *args, **kwargs: SimpleNamespace(returncode=0))
    assert commits.closed_attempt(ticket) == reference
    replacement = tmp_path / 'replacement'
    replacement.mkdir()
    resumed_commits = fix_tests_git.RepairCommits(tmp_path, replacement)
    resumed_commits.state = dict(commits.state)
    proof = commits.closeout_proof()
    (replacement / 'closed-git-proof.json').write_text(json.dumps(proof))
    (journal / 'progress.json').unlink()  # Original allocation can now retire.
    assert resumed_commits.closed_attempt(ticket) == reference
    receipt['ownership']['accepted_attempt'] = '0' * 32
    (replacement / 'closed-git-proof.json').write_text(json.dumps(receipt))
    assert resumed_commits.closed_attempt(ticket) is None


def test_public_repair_keeps_dirty_suspension_owned_on_resume(
        tmp_path, monkeypatch, isolated_source, _controlled_public_repair):
    import fix_tests
    import test_source
    import vm_test_queue
    from launcher_runtime import TaskBudget

    control = _controlled_public_repair
    control.response.update(status='stalled', summary='Cannot repair this input.', verification_case=None)
    # A final tier's stalled turn is terminal rather than another escalation.
    monkeypatch.setattr(fix_tests, 'next_tier', lambda model, effort, **kwargs: (model, effort))
    resumed = False
    class Execution:
        drained = True
        failure = None
        def refresh_impact(self):
            pass  # This fixture's impact is already current.
        def attempt(self, purpose, target=None):
            control.order.append(purpose)
            return dict(status=0 if resumed else 1, accepted=resumed,
                        reference=dict(accepted=resumed))
    def execute(root, args, *, actions, **kwargs):
        assert actions['admit_task']('unit')
        if not resumed:
            actions['triage'](control.ticket, {})
        result = actions['repair'](control.ticket, Execution())
        assert result == dict(outcome='suspended')
        return dict(status=1, suspended=True)
    monkeypatch.setattr(vm_test_queue, 'run', execute)
    with pytest.raises(fix_tests.ControllerReload):
        control.worker()
    assert control.order == ['triage', 'recheck', 'repair']

    resumed = True
    monkeypatch.setattr(test_source, '_generations', {})
    assert control.worker(reloading=True) == 1
    # A further resume still owns the edited ticket, even if a no-edit recheck
    # could now pass. It may seek a repair, but cannot settle or release it.
    assert control.worker(reloading=True) == 1
    saved = control.saved()
    entry = saved['repairs']['["unit", "exact", ""]']
    assert entry['terminal_failure'].startswith('repair stalled:')
    assert saved['active_ticket'] == control.ticket['id']
    assert saved.get('pending') is None
    assert isolated_source.owner() == str(control.run)
    assert control.gate.fd is not None
    assert control.order.count('recheck') == 1
    assert 'verification' not in control.order and 'closeout' not in control.order
    assert TaskBudget(control.run).read()['completed'] == 0


@pytest.mark.parametrize('failed', [False, True])
def test_public_task_limit_preserves_the_coordinator_verdict(
        tmp_path, monkeypatch, isolated_source, _controlled_public_repair, failed):
    import fix_tests
    import vm_test_queue
    from regression_process import Control
    from launcher_runtime import TaskBudget

    current = _controlled_public_repair
    TaskBudget(current.run).initialize(1)
    monkeypatch.setattr(fix_tests, 'requested_inventory', lambda *args, **kwargs:
                        {'backend': {'args': []}, 'static': {'args': ['shell']}})
    monkeypatch.setattr(commands, 'selections', lambda *args:
                        [('backend', []), ('static', ['shell'])])
    def execute(root, args, *, actions, pass_identity, **kwargs):
        def host(assignment=None, *, categories):
            assert assignment is None
            admitted = [kind for kind in ('backend', 'static')
                        if kind in categories and actions['admit_task'](kind)]
            assert admitted == ['backend']
            value = dict(status=int(failed), limited=True, complete=False,
                         denied_categories=['static'], completed_categories=[] if failed else ['backend'])
            if failed:
                value['failure_work'] = dict(category='backend', options=[], cases=[], case=None, area=False)
            return value
        actions = dict(actions,
            triage=lambda *args: dict(source=vm_test_queue.source_identity(root), evidence_digest='e' * 64,
                decision=dict(impact='no', reason='Only this private check.', scope=['backend'],
                              evidence=['Independent static input.'], classification='test_issue')),
            repair=lambda *args: dict(outcome='leave_failed'))
        plan = (dict(concurrency=1), [], ['backend', 'static', 'shell'], [], [], {})
        result = vm_test_queue.execute_pass(root, plan, Control(), lambda *args: None,
            host=host, actions=actions, pass_identity=pass_identity)
        assert result['limited'] and result['status'] == int(failed)
        return result
    monkeypatch.setattr(vm_test_queue, 'run', execute)
    assert current.worker() == int(failed)
    assert TaskBudget(current.run).read()['completed'] == 1
    assert current.saved()['rounds']['done'] is failed


def test_logical_task_admission_survives_resume_and_limit_changes(tmp_path, monkeypatch):
    from launcher_runtime import TaskBudget

    budget = TaskBudget(tmp_path)
    budget.initialize(3)
    assert budget.admit(key='round-1:system', concurrent=True)
    assert budget.admit(key='round-1:e2e', concurrent=True)
    resumed = TaskBudget(tmp_path)
    resumed.set_limit(1)
    assert resumed.admit(key='round-1:system', concurrent=True)
    assert resumed.admit(key='round-1:e2e', concurrent=True)
    assert resumed.complete(key='round-1:system')
    assert not budget.complete(key='round-1:system')
    assert budget.complete(key='round-1:e2e')
    assert not budget.admit(key='round-2:all', concurrent=True)
    assert budget.admit(key='round-1:e2e', concurrent=True)
    assert budget.read()['started'] == budget.read()['completed'] == 2
    with pytest.raises(ValueError, match='no admission'):
        budget.complete(key='round-2:all')

    # The public resume parser must permit the same replacement without
    # changing saved selectors or rounds before the budget can apply it.
    import fix_tests
    import test_checkpoint
    from vm_selection import VARIABLE, BATCH
    for name in (VARIABLE, BATCH):
        monkeypatch.setenv(name, os.environ.get(name, ''))
    monkeypatch.setattr(test_checkpoint, 'request_record', lambda *args: dict(
        categories=['unit'], vm=None, rounds=2, model=None, effort=None, tasks=1))
    admitted = []
    monkeypatch.setattr(fix_tests, 'select', lambda root, **options:
                        admitted.append(options) or (tmp_path, True))
    monkeypatch.setattr(fix_tests.detached_launcher, 'report_start', lambda *args, **kwargs: 0)
    assert fix_tests.main(['--resume', '--tasks', '2']) == 0
    assert admitted[0]['tasks'] == 2 and admitted[0]['rounds'] == 2
    assert admitted[0]['categories'] == ['unit'] and admitted[0]['resume'] is True


def test_coordinator_host_continues_after_isolated_failure(tmp_path, monkeypatch, isolated_source):
    import threading
    import vm_test_queue

    source = dict(digest='a' * 64, generation=0)
    monkeypatch.setattr(vm_test_queue, 'source_identity', lambda _: dict(source))
    monkeypatch.setattr(commands, 'selections', lambda root, args:
                        [('unit', ['-k', 'selected']), ('static', [])])
    inventories = []
    def inventory(root, work, control, *, vm):
        inventories.append((dict(work), vm))
        return ['selected::current']
    monkeypatch.setattr(vm_test_queue, 'repair_case_inventory', inventory)
    events, settled = [], []
    original = dict(category='unit', options=['-k', 'selected'], cases=['removed::case'],
                    case='removed::case', area=False)
    def host(assignment=None, *, categories=None):
        if assignment is not None:
            assert assignment['vm'] == '' and assignment['work'] == original
            assert assignment['execution'] == dict(original, case='selected::current', cases=['selected::current'])
            events.append('bounded recheck')
            return dict(status=0, evidence=dict(assignment, passed=['selected::current'],
                                                cleanup=True, diagnostic=False))
        events.append(tuple(sorted(categories)))
        if len(events) == 1:
            return dict(status=1, failure_work=original, completed_categories=[])
        return dict(status=0, completed_categories=sorted(categories))
    def triage(ticket, result):
        events.append('triage')
        return dict(source=source, evidence_digest='b' * 64,
                    decision=dict(impact='no', reason='Private selected input.', scope=['selected input'],
                                  evidence=['Other inputs unchanged.'], classification='test_issue'))
    def repair(ticket, execution):
        assert execution.drained
        assert events[-1] == ('static',), 'isolated repair ran before pending normal work'
        result = execution.attempt('recheck')
        assert result['accepted']
        return dict(outcome='resolved', attempt=result['reference'])
    plan = (dict(concurrency=1, vms=[]), (), ['unit', '-k', 'selected', 'static'], [], [], {})
    outcome = vm_test_queue.execute_pass(tmp_path, plan,
        SimpleNamespace(stopped=threading.Event()), Mock(), host=host,
        actions=dict(triage=triage, repair=repair, settle_task=settled.append))
    assert outcome['status'] == 0 and not outcome['suspended']
    assert events == [('static', 'unit'), 'triage', ('static',), 'bounded recheck', ('unit',)]
    assert sorted(settled) == ['static', 'unit']
    assert inventories == [(original, None)]
    with isolated_source.state():
        assert not isolated_source.impact_holds()


@pytest.mark.parametrize('selected,total', [(True, 6), (False, 3)])
def test_run_wide_rounds_resume_and_repeat_changed_verification(tmp_path, selected, total):
    import fix_tests
    from launcher_runtime import TaskBudget

    budget = TaskBudget(tmp_path)
    budget.initialize(None)
    state, calls, saved = {}, [], []
    current_source = dict(digest='a' * 64, generation=0)
    def save():
        saved.append(json.loads(json.dumps(state)))
    def execute(categories, **options):
        calls.append((state['round'], options['pass_identity'], options['resume']))
        assert saved[-1]['resume'] is True
        for category in categories:
            assert options['admit_task'](category)
            assert options['admit_task'](category)  # A second family shares the task.
            options['settle_task'](category)
        if len(calls) == 1:
            return dict(status=130)  # Resume keeps this pass and its admissions.
        if len(calls) == 3:
            current_source.update(digest='b' * 64, generation=1)
            return dict(status=0, source_changed=True)
        return dict(status=0)
    def run():
        return fix_tests.run_rounds(['system', 'e2e'], execute, rounds=2, selected=selected,
            state=state, save=save, budget=budget, source=lambda: dict(current_source))

    assert run()['status'] == 130
    assert not state['done']
    assert run()['status'] == 0
    assert [number for number, _, _ in calls] == [1, 1, 2, 2]
    assert calls[0][1] == calls[1][1]
    assert calls[0][2] is False and calls[1][2] is True
    assert calls[2][1] != calls[3][1] and calls[2][0] == calls[3][0]
    assert budget.read()['started'] == budget.read()['completed'] == total
    assert run()['status'] == 0 and len(calls) == 4


def test_completed_rounds_do_not_repeat_for_later_external_edits(tmp_path):
    import fix_tests
    from launcher_runtime import TaskBudget

    budget = TaskBudget(tmp_path)
    budget.initialize(None)
    state, calls = {}, []
    source = dict(digest='a' * 64, generation=0)
    def execute(categories, **options):
        calls.append(state['round'])
        assert options['admit_task']('system')
        options['settle_task']('system')
        source.update(digest=str(state['round']) * 64, generation=state['round'])
        return dict(status=0)
    result = fix_tests.run_rounds(['system'], execute, rounds=2, selected=False,
        state=state, save=lambda: None, budget=budget, source=lambda: dict(source))
    assert result['status'] == 0 and state['done'] and calls == [1, 2]
    assert state['source'] != source  # Keep the completed pass's provenance.
    assert budget.read()['started'] == budget.read()['completed'] == 2


def test_run_wide_terminal_failure_waits_for_suspended_repair(tmp_path):
    import fix_tests
    from launcher_runtime import TaskBudget

    budget = TaskBudget(tmp_path)
    budget.initialize(1)
    state, calls = {}, []
    def execute(categories, **options):
        calls.append((options['pass_identity'], options['resume']))
        assert options['admit_task']('system')
        pending = len(calls) == 1
        if not pending:
            options['settle_task']('system')
        return dict(status=1, limited=True, terminal_failed=True,
                    pending_repairs=pending, suspended=pending)
    def run():
        return fix_tests.run_rounds(['system'], execute, rounds=2, selected=True,
            state=state, save=lambda: None, budget=budget,
            source=lambda: dict(digest='a' * 64, generation=0))
    assert run()['status'] == 1 and not state['done']
    assert run()['status'] == 1 and state['done']
    assert calls[0][0] == calls[1][0] and calls[1][1] is True
    assert budget.read()['started'] == budget.read()['completed'] == 1
    assert run()['status'] == 1 and len(calls) == 2


def test_baseline_queue_cancels_pending_work_and_refreshes_after_checkin(tmp_path, monkeypatch):
    """A cancelled baseline replacement finishes before helper refresh."""
    from contextlib import contextmanager
    import threading
    import regression_process
    import test_source
    import vm_pool
    import host_compute
    monkeypatch.setattr(host_compute, 'launch', lambda vms: nullcontext(vms))
    from vm_selection import vm_config

    vms = tuple(vm_config.VMConfig(name, tmp_path / name, enabled=True)
                for name in ('one', 'two', 'three'))
    configured = {vm.name: vm for vm in vms}
    monkeypatch.setattr(vm_config, 'load', configured.__getitem__)
    monkeypatch.setattr(vm_config, 'execution', lambda _, **kwargs: (3, vms))
    monkeypatch.setattr(test_source, 'startup', lambda *a, **k: nullcontext())
    monkeypatch.setattr(test_source, 'reader', lambda *a, **k: nullcontext())
    monkeypatch.setattr(test_source, 'finish_admission', lambda: None)
    launcher = runpy.run_path(str(ROOT / 'tools/prepare-vm'))
    main = launcher['main']
    monkeypatch.setitem(main.__globals__, 'read_password', lambda: None)
    monkeypatch.setitem(main.__globals__, 'check', lambda _: None)
    monkeypatch.setitem(main.__globals__, 'tool_host', lambda _: vms[0].host)
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    held, calls, refreshes = set(), [], []
    stopped = threading.Event()

    @contextmanager
    def reservation(name, *, stopped, bind):
        assert not bind
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
        name = env[vm_config.VARIABLE]
        assert name in held
        assert env[vm_pool.VARIABLE] == name + '-receipt'
        assert control.stopped is not stopped  # Baseline has no stop protocol.
        calls.append(name)
        if len(calls) == 1:
            return 1  # Failure must not prevent the next preparation.
        stopped.set()
        assert not control.stopped.is_set()
        return 0  # Active replacement finishes despite outer cancellation.

    def refresh(command, **kwargs):
        assert not held, 'helper refresh ran before VM checkin'
        assert command == [str(ROOT / 'setup.sh'), '--test-tools-only']
        refreshes.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(vm_pool, 'reservation', reservation)
    monkeypatch.setattr(regression_process.Control, 'installed', installed)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    monkeypatch.setattr(subprocess, 'run', refresh)
    assert main(['--mode', 'auto', '--vm', 'one,two,three', '--y']) == 130
    assert len(calls) == 2 and len(refreshes) == 1
    assert not held


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


def test_checkout_source_writer_drains_readers_and_shares_generation(tmp_path):
    import detached_launcher as launcher
    from test_source import SourceProtection

    first = SourceProtection(tmp_path)
    independent = SourceProtection(tmp_path)
    owner = str(tmp_path / 'repair')
    with launcher.lock(tmp_path / 'repair-owner') as writer:
        with launcher.lock(tmp_path / 'repair-owner') as reader:
            with first.state():
                assert first.admit(reader)
            with independent.state():
                assert not independent.admit(writer, owner=owner)
            assert first.owner() is None
        with independent.state():
            assert not independent.admit(writer, owner=owner, ready=lambda: False)
            assert first.owner() is None
        with launcher.lock(tmp_path / 'repair-owner') as reader, first.state():
            assert first.admit(reader)  # Waiting isolated work published no intent.
        with independent.state():
            assert independent.admit(writer, owner=owner, ready=lambda: True)
            independent.finish(owner, changed=True)
    assert first.generation() == independent.generation() == 1
    with launcher.lock(tmp_path / 'repair-owner') as reader, first.state():
        assert first.admit(reader)


def test_checkout_source_retains_crashed_and_cancelled_writer(tmp_path):
    import detached_launcher as launcher
    from test_source import SourceProtection

    owner = str(tmp_path / 'repair')
    crash = '''import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from detached_launcher import lock
from test_source import SourceProtection
directory = Path(sys.argv[2])
source = SourceProtection(directory)
with lock(directory / 'repair-owner') as descriptor, source.state():
    assert source.admit(descriptor, owner=sys.argv[3])
    os._exit(0)
'''
    subprocess.run([sys.executable, '-B', '-c', crash, str(ROOT / 'tools'),
                    str(tmp_path), owner], check=True, timeout=10)
    source = SourceProtection(tmp_path)
    pending = tmp_path / 'repair-source-pending.json'
    before = pending.read_bytes()
    assert source.owner() == owner
    with launcher.lock(tmp_path / 'repair-owner') as descriptor, source.state():
        with pytest.raises(ValueError, match='unfinished repair'):
            source.admit(descriptor)
        with pytest.raises(ValueError, match='unfinished repair'):
            source.admit(descriptor, owner=str(tmp_path / 'foreign'))
        with pytest.raises(ValueError, match='ownership changed'):
            source.finish(str(tmp_path / 'foreign'), changed=True)
        assert pending.read_bytes() == before
        assert source.generation() == 0
        assert source.admit(descriptor, owner=owner)
        source.finish(owner, unfinished=True)
    assert pending.read_bytes() == before
    restarted = SourceProtection(tmp_path)
    with launcher.lock(tmp_path / 'repair-owner') as descriptor, restarted.state():
        assert restarted.admit(descriptor, owner=owner)
        restarted.finish(owner, changed=True)
    assert not pending.exists()
    assert source.generation() == 1


def test_checkout_source_fences_startup_and_borrows_writer_through_reload(tmp_path):
    import detached_launcher as launcher
    import test_source

    source = test_source.SourceProtection(tmp_path)
    owner = str(tmp_path / 'repair')
    probe = tmp_path / 'startup.py'
    witness = tmp_path / 'imports'
    probe.write_text('''import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import test_source
import launcher_reload
directory = Path(sys.argv[2])
test_source.source_directory = lambda root: directory
with test_source.reader(directory) as descriptor:
    with Path(sys.argv[3]).open('a') as stream:
        stream.write(sys.argv[4] + '\\n')
    assert descriptor in test_source.descriptors()
    if sys.argv[4] == 'startup':
        launcher_reload.replace([sys.executable, '-B', __file__, *sys.argv[1:4], 'reload'],
                                test_source.descriptors())
''')
    command = [sys.executable, '-B', str(probe), str(ROOT / 'tools'),
               str(tmp_path), str(witness), 'startup']
    environment = dict(os.environ)
    for key in (test_source.VARIABLE, test_source.WRITER,
                'ONPC_LAUNCHER_RELOAD_BASELINE', 'ONPC_VM_RELOAD_KEEPER'):
        environment.pop(key, None)
    with launcher.lock(tmp_path / 'repair-owner') as descriptor:
        with source.state():
            assert source.admit(descriptor, owner=owner)
        # After a crash the kernel lease is gone, but startup still must refuse
        # before entering the guarded body from the unfinished checkout.
    refused = subprocess.run(command, env=environment, capture_output=True,
                             text=True, timeout=10)
    assert refused.returncode != 0 and 'unfinished repair' in refused.stderr
    assert not witness.exists()
    with launcher.lock(tmp_path / 'repair-owner') as descriptor:
        with source.state():
            assert source.admit(descriptor, owner=owner)
        environment.update({test_source.VARIABLE: str(descriptor), test_source.WRITER: owner})
        subprocess.run(command, env=environment, pass_fds=(descriptor,),
                       check=True, timeout=10)
        assert witness.read_text().splitlines() == ['startup', 'reload']
        assert source.owner() == owner
        with source.state():
            source.finish(owner)


@pytest.fixture
def isolated_source(tmp_path, monkeypatch):
    import threading
    import test_source

    # This checkout owns only its private leases, never the outer test runner's.
    for name in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS,
                 test_source.STARTUP_READER, test_source.STARTUP_WRITER):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(test_source, '_local', threading.local())
    monkeypatch.setattr(test_source, '_generations', {})
    monkeypatch.setattr(test_source, 'source_directory', lambda root, **options: tmp_path)
    return test_source.SourceProtection(tmp_path)


def test_checkout_source_impact_holds_fence_normal_work_but_allow_triage(
        tmp_path, isolated_source):
    import detached_launcher as launcher
    import test_source

    source = isolated_source
    independent = test_source.SourceProtection(tmp_path)
    first, second = (str(tmp_path / name) for name in ('first-ticket', 'second-ticket'))
    with test_source.reader(tmp_path, wait=False) as admitted:
        with source.state():
            source.set_impact(first, 'untriaged')
            source.set_impact(second, 'unsure')
        # A finite operation retains its admitted source through owned cleanup.
        with test_source.reader(tmp_path, wait=False) as cleanup:
            assert cleanup == admitted
    with pytest.raises(test_source.SourceBusy):
        with test_source.reader(tmp_path, wait=False):
            pytest.fail('normal work crossed a pending impact hold')
    with source.state():
        independent.set_impact(first, 'no')
        assert source.impact_holds() == {second: 'unsure'}
        independent.set_impact(first, 'yes')
        with pytest.raises(ValueError, match='impact decision'):
            source.set_impact(second, 'typo')
        assert source.impact_holds() == {first: 'yes', second: 'unsure'}
    # Both pending holds may be triaged promptly; neither can strand the other.
    with test_source.reader(tmp_path, impact_ticket=second, wait=False):
        with pytest.raises(ValueError, match='held ticket'):
            with test_source.reader(tmp_path, impact_ticket=str(tmp_path / 'unknown'), wait=False):
                pytest.fail('borrowed source accepted an unknown triage ticket')
    with pytest.raises(ValueError, match='held ticket'):
        with test_source.reader(tmp_path, impact_ticket=str(tmp_path / 'unknown'), wait=False):
            pytest.fail('unknown ticket bypassed normal admission')
    with launcher.lock(tmp_path / 'repair-owner') as writer:
        with source.state():
            assert source.admit(writer, owner=first)
        with pytest.raises(test_source.SourceBusy):
            with test_source.reader(tmp_path, impact_ticket=second, wait=False):
                pytest.fail('triage read an active writer')
        test_source.retain(writer, first)
        try:
            with pytest.raises(test_source.SourceBusy, match='cannot borrow a writer'):
                with test_source.reader(tmp_path, impact_ticket=second, wait=False):
                    pytest.fail('read-only triage borrowed an active writer')
            with test_source.reader(tmp_path, wait=False) as verification:
                assert verification == writer
        finally:
            test_source.forget(writer)
        with source.state():
            source.finish(first, unfinished=True)
    # A crashed/cancelled writer stays fenced even for an otherwise valid triage.
    with pytest.raises(test_source.SourceBusy, match='unfinished repair'):
        with test_source.reader(tmp_path, impact_ticket=second, wait=False):
            pytest.fail('triage read retained unverified edits')
    with launcher.lock(tmp_path / 'repair-owner') as writer, source.state():
        assert source.admit(writer, owner=first)
        source.finish(first)
        source.release_impact(first)
        assert independent.impact_holds() == {second: 'unsure'}
        source.release_impact(second)
    with test_source.reader(tmp_path, wait=False):
        pass
    with source.state():
        source.set_impact(first, 'no')
        assert independent.impact_holds() == {}
    with test_source.reader(tmp_path, impact_ticket=first, wait=False):
        pass  # An inactive pending ticket can still retriage changed inputs.
    with test_source.reader(tmp_path, wait=False):
        pass
    with launcher.lock(tmp_path / 'repair-owner') as writer, independent.state():
        assert independent.admit(writer, owner=second)
        independent.finish(second, changed=True)
        assert source.impact_holds() == {first: 'unsure'}
    with pytest.raises(test_source.SourceBusy):
        with test_source.reader(tmp_path, wait=False):
            pytest.fail('an independent source change kept stale isolation admission open')
    with test_source.reader(tmp_path, impact_ticket=first, wait=False, fresh=True):
        pass
    with source.state():
        source.release_impact(first)
    with launcher.lock(tmp_path / 'repair-owner') as writer, independent.state():
        assert independent.admit(writer, owner=second)
        independent.finish(second, changed=True)
        assert source.impact_holds() == {}  # Settled tickets never return.
    with test_source.reader(tmp_path, wait=False, fresh=True):
        pass


def test_checkout_source_impact_updates_preserve_readable_state(tmp_path, isolated_source, monkeypatch):
    import detached_launcher as launcher
    import test_source

    source = isolated_source
    path = tmp_path / 'repair-impact-holds.json'
    records = {str(tmp_path / (f'ticket-{index:04d}-' + 'x' * 80)):
               {'hold': 'unsure', 'generation': 0} for index in range(512)}
    launcher.atomic(path, records)
    assert path.stat().st_size > 65536
    with source.state():
        source.set_impact(str(tmp_path / 'new-ticket'), 'no')
        assert len(source.impact_holds()) == len(records)
        previous = path.read_bytes()
        monkeypatch.setattr(test_source, 'IMPACT_MAX_BYTES', len(previous) + 256)
        with pytest.raises(ValueError, match='oversized'):
            source.set_impact(str(tmp_path / ('large-ticket-' + 'x' * 240)), 'unsure')
        assert path.read_bytes() == previous
        source.release_impact(next(iter(records)))
        assert len(source.impact_holds()) == len(records) - 1


def test_checkout_source_forwards_only_the_calling_workers_lease(tmp_path, isolated_source):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import test_source
    from test_storage import scratch_descriptors
    from watch_recording_worker import shared_owner_descriptors

    overlap = threading.Barrier(2, timeout=5)
    def admitted():
        with test_source.reader(tmp_path) as descriptor:
            overlap.wait()
            assert test_source.descriptors() == (descriptor,)
            assert test_source.environment() == {test_source.VARIABLE: str(descriptor)}
            assert set(shared_owner_descriptors()) == set(scratch_descriptors()) - {descriptor}
            overlap.wait()
            return descriptor
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(admitted) for _ in range(2)]
        descriptors = [future.result(timeout=10) for future in futures]
    assert len(set(descriptors)) == 2
    assert test_source.descriptors() == ()


def test_checkout_source_startup_release_clears_aliases_but_keeps_adopted_writer(
        tmp_path, monkeypatch, isolated_source):
    import detached_launcher as launcher
    import test_source

    source = isolated_source
    with launcher.lock(tmp_path / 'repair-owner') as descriptor:
        with source.state():
            assert source.admit(descriptor)
        startup = os.dup(descriptor)
        monkeypatch.setenv(test_source.VARIABLE, str(startup))
        monkeypatch.setenv(test_source.STARTUP_READER, str(startup))
        monkeypatch.setenv(test_source.IMPORTS, str(startup))
        test_source.finish_imports(tmp_path)
        assert test_source.environment() == {} and test_source.descriptors() == ()
        assert test_source.STARTUP_READER not in os.environ and test_source.IMPORTS not in os.environ
        with pytest.raises(OSError):
            os.fstat(startup)

        owner = str(tmp_path / 'repair')
        with source.state():
            assert source.admit(descriptor, owner=owner)
        monkeypatch.setenv(test_source.VARIABLE, str(descriptor))
        monkeypatch.setenv(test_source.WRITER, owner)
        monkeypatch.setenv(test_source.STARTUP_READER, str(descriptor))
        try:
            with test_source.reader(tmp_path):
                # RepairGate may adopt a startup writer before the borrowed
                # import context leaves. That new registration must survive.
                test_source.retain(descriptor, owner)
            test_source.finish_imports(tmp_path, keep=(descriptor,))
            assert test_source.descriptors() == (descriptor,)
            assert test_source.environment()[test_source.WRITER] == source.owner() == owner
            source.validate(descriptor, held=True, writer=True)
        finally:
            test_source.forget(descriptor)
            with source.state():
                source.finish(owner)

    # A reexec bootstrap may borrow EX for resume, but its owner label alone
    # does not adopt that descriptor as the new controller's retained writer.
    with launcher.lock(tmp_path / 'repair-owner') as descriptor:
        with source.state():
            assert source.admit(descriptor, owner=owner)
        bootstrap = os.dup(descriptor)
    monkeypatch.setenv(test_source.VARIABLE, str(bootstrap))
    monkeypatch.setenv(test_source.WRITER, owner)
    monkeypatch.setenv(test_source.IMPORTS, str(bootstrap))
    with test_source.admission(tmp_path, ['--resume'], repair=True):
        test_source.finish_admission()
        assert test_source.descriptors() == () and test_source.environment() == {}
        with pytest.raises(OSError):
            os.fstat(bootstrap)
    assert source.owner() == owner
    with launcher.lock(tmp_path / 'repair-owner') as descriptor, source.state():
        assert source.admit(descriptor, owner=owner)
        source.finish(owner)


def test_checkout_source_generation_reloads_through_repair_continuation(tmp_path, isolated_source):
    import detached_launcher as launcher
    import launcher_reload
    from test_source import RepairGate

    gate = RepairGate(tmp_path)
    with gate.source():
        pass
    owner = str(tmp_path / 'independent-repair')
    with launcher.lock(tmp_path / 'repair-owner') as writer, isolated_source.state():
        assert isolated_source.admit(writer, owner=owner)
        isolated_source.finish(owner, changed=True)
    retained = []
    class Continuation(launcher_reload.ReloadRequested):
        pass
    def keep_continuation():
        retained.append('original admission')
        raise Continuation()
    gate.on_reload = keep_continuation
    with launcher_reload.watching(tmp_path), pytest.raises(Continuation):
        with gate.source():
            pytest.fail('stale repair code must not execute another case')
    assert retained == ['original admission']
    with launcher.lock(tmp_path / 'repair-owner') as reader, isolated_source.state():
        assert isolated_source.admit(reader)  # Reload left no hidden reader/writer.


def test_checkout_source_resume_cannot_recreate_a_finished_writers_fence(
        tmp_path, monkeypatch, isolated_source):
    import fcntl
    import detached_launcher as launcher
    import test_source

    source = isolated_source
    owner = str(tmp_path / 'repair')
    with launcher.lock(tmp_path / 'repair-owner') as writer:
        with source.state():
            assert source.admit(writer, owner=owner)
        waited = []
        def finish_while_waiting(_):
            waited.append(True)
            with source.state():
                source.finish(owner)
                fcntl.flock(writer, fcntl.LOCK_UN)
        monkeypatch.setattr(test_source, 'time', SimpleNamespace(sleep=finish_while_waiting))
        with test_source.startup(tmp_path, ['--resume'], repair=True):
            assert waited == [True]
            assert source.owner() is None
            assert test_source.WRITER not in test_source.environment()
        assert not (tmp_path / 'repair-source-pending.json').exists()


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
with _lock(source.directory / 'repair-owner') as descriptor:
    with source.state():
        assert source.admit(descriptor, owner=sys.argv[3] or None)
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
    for owner in (None, str(tmp_path / 'repair')):
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
                with launcher.lock(tmp_path / 'repair-owner') as writer, isolated_source.state():
                    assert not isolated_source.admit(writer, owner=owner or str(tmp_path / 'other'))
                child.communicate(timeout=5)
                assert child.returncode == 0
                with launcher.lock(tmp_path / 'repair-owner') as writer, isolated_source.state():
                    assert isolated_source.admit(writer, owner=owner)
                    if owner is not None:
                        isolated_source.finish(owner)
            finally:
                caller.communicate(timeout=5)
                if child is not None:
                    child.communicate(timeout=5)


@pytest.mark.parametrize('scope,host_only', [
    ('UI obligation; feedback sending', True), ('Cases 156; installed feedback', False),
])
def test_write_e2e_task_acceptance_keeps_host_and_installed_distinct(
        tmp_path, monkeypatch, scope, host_only):
    import write_e2e as workflow
    from execution_plan import Plan
    from tests.support.write_e2e_fixtures import reply
    monkeypatch.setattr(workflow, 'PLAN', 'plan.md')
    monkeypatch.setattr(workflow, 'QUEUE', 'queue.md')
    (tmp_path / 'plan.md').write_text('Next task: **001 — First**.\n')
    (tmp_path / 'first.md').write_text('First task')
    (tmp_path / 'second.md').write_text('Second task')
    (tmp_path / 'queue.md').write_text(
        f'| [ ] | 001 | [First](first.md) | Baseline | {scope} |\n'
        '| [ ] | 002 | [Second](second.md) | 001 | Later |\n')
    task = Plan(tmp_path, 'plan.md', 'queue.md').tasks()[0]
    assert task.ui_obligation == host_only
    state = dict(workflow.fresh_state('001'), task_scope=task.scope)
    prompt = workflow.session_prompt(state)
    assert ('Return task_complete with\nhost_validated true and live_result not_run' in prompt) == host_only
    before = workflow.queue_state(tmp_path)[1]
    (tmp_path / 'queue.md').write_text((tmp_path / 'queue.md').read_text().replace('[ ] | 001', '[x] | 001'))
    (tmp_path / 'plan.md').write_text('Next task: **002 — Second**.\n')
    result = reply('task_complete', 'not_run')
    if host_only:
        assert workflow.accept_result(tmp_path, state, result, before)['phase'] == 'complete'
        with pytest.raises(ValueError, match='acceptance'):
            workflow.accept_result(tmp_path, dict(state, acceptance={'live_result': 'failed'}), result, before)
        with pytest.raises(ValueError, match='acceptance'):
            workflow.accept_result(tmp_path, state, dict(result, host_validated=False), before)
    else:
        with pytest.raises(ValueError, match='acceptance'):
            workflow.accept_result(tmp_path, state, result, before)
        assert workflow.accept_result(tmp_path, state, reply('task_complete', 'passed'), before)['phase'] == 'complete'


def test_write_e2e_host_selection_never_reads_vm_configuration(tmp_path, monkeypatch):
    import write_e2e as workflow
    import vm_selection
    selected = Mock(return_value=(1, []))
    monkeypatch.setattr(vm_selection, 'execution_selection', selected)
    monkeypatch.setattr(vm_selection, 'execution_binding', lambda: 'installed-target')
    monkeypatch.setenv(vm_selection.VARIABLE, 'stale-target')
    monkeypatch.setenv(vm_selection.BATCH, '{}')
    assert vm_selection.task_selection(host_only=True) is None
    selected.assert_not_called()
    assert vm_selection.VARIABLE not in os.environ and vm_selection.BATCH not in os.environ
    monkeypatch.setattr(workflow, 'PLAN', 'plan.md')
    monkeypatch.setattr(workflow, 'QUEUE', 'queue.md')
    (tmp_path / 'plan.md').write_text('Next task: **001 — First**.\n')
    (tmp_path / 'queue.md').write_text(
        '| [ ] | 001 | [First](first.md) | Baseline | UI obligation; synthetic sending |\n')
    (tmp_path / 'first.md').write_text('Host acceptance')
    monkeypatch.setattr(workflow, 'initial_state', lambda *a, **k: workflow.fresh_state('001'))
    monkeypatch.setattr(workflow, 'session_command', lambda *a, **k: Mock())
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda *a: None)
    run = tmp_path / 'run'
    run.mkdir()

    def launch(root, kind, command, **options):
        argv = command(run, 0)
        state = json.loads(argv[-1])
        assert state['vm'] is None and workflow.host_only(state)
        options['on_start'](run)
        assert json.loads((run / 'vm.json').read_text()) == {'vm': None}
        return run, True

    monkeypatch.setattr(workflow.launcher, 'select', launch)
    assert workflow.select(tmp_path, []) == (run, True)
    selected.assert_not_called()
    assert vm_selection.task_selection('explicit-target') == 'installed-target'
    selected.assert_called_once_with('explicit-target')


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
    execute = Mock(side_effect=[build_status, 0])
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
        assert execute.call_count == 2
        authorize.assert_called_once_with('/usr/local/libexec/onpc-test-runner')
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
        assert capsys.readouterr().out.strip() == 'run-tests: output=' + str(candidate)
    else:
        assert result == 0
        assert control.run.call_args.args[0] == [
            '/usr/bin/python3', '-B', str(ROOT / 'tools/build_test_artifacts.py'),
            *(['--reuse'] if package_format == 'deb' else []),
            '--package-format', package_format, '--build-target', target.name,
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
    family = 'fedora44-x86_64' if package_format == 'rpm' else 'ubuntu26.04-x86_64'
    configured = replace(vm_artifacts.selected(), family=family, package_format=package_format)
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: configured)
    target = configured.require_build_target()
    monkeypatch.setattr(vm_artifacts, 'check', Mock())
    output = tmp_path / 'output'
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    verify = Mock(return_value={'packages': {'current': {
        'architecture': {'deb': 'amd64', 'rpm': 'x86_64'}[package_format],
        'version': '1.4-0.1.dev.fc44' if package_format == 'rpm' else '1.4'}}})
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


def test_named_artifact_allocation_is_exclusive_private_and_retained(tmp_path, monkeypatch):
    import test_retention

    output = tmp_path / 'new-output'
    monkeypatch.setattr(commands, 'artifact_output', lambda _: str(output))
    with test_retention.Store(tmp_path / 'retention').session():
        assert commands.allocate_artifact_output('/tmp/onpc-input') == str(output)
        assert output.stat().st_mode & 0o777 == 0o700
        (output / 'preserve').write_text('existing input')
        with pytest.raises(FileExistsError):
            commands.allocate_artifact_output('/tmp/onpc-input')
        assert (output / 'preserve').read_text() == 'existing input'
    assert str(output) in (tmp_path / 'retention/current.json').read_text()


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


def test_retention_permission_failure_identifies_allocation_without_starting_tests(
        tmp_path, monkeypatch, capsys, vm_execution_branch):
    import regression
    import test_retention
    import vm_selection

    import test_activity
    # Exercise the worker's retention gate directly. Public VM selections now
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
    monkeypatch.setattr(regression, 'retained_main',
                        lambda *args, **kwargs: pytest.fail('tests started despite inaccessible storage'))
    try:
        assert commands._main(['all', *VM_ARGS]) == 2
        diagnostic = capsys.readouterr().err
        assert 'PermissionError' in diagnostic
        assert 'retention: cannot inspect registered allocation' in diagnostic
        assert repr(str(scratch)) in diagnostic
        assert 'startup refused' in diagnostic
        assert 'filesystem or execution failure' not in diagnostic
        assert journal.read_bytes() == original
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


def test_pytest_storage_does_not_inherit_ramdisk_or_caller_override(checkout, monkeypatch):
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        monkeypatch.setenv(key, '/tmp/untrusted')
    env = host.test_environment(checkout)
    from pathlib import Path
    assert Path(env['TMPDIR']).is_relative_to(ROOT / 'output/test-runs/host/scratch')
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
    subprocess.run([sys.executable, '-B', str(probe)], env=env, check=True, timeout=10)
    assert host.environment(checkout)['TMPDIR'] == env['TMPDIR']


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


def test_e2e_listing_is_host_safe_and_pending_execution_refused(monkeypatch):
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
