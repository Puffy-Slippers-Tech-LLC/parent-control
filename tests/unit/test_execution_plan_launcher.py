"""Private plan fixtures exercise shared selection, recovery, budgets and panes."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tomllib
from types import SimpleNamespace

import pytest

import launcher_git
from execution_plan import Plan, local_file
from launcher_display import TaskDisplay
from launcher_runtime import TaskBudget, task_limit, task_progress, warn_remaining
from launcher_view import WorkflowView, plan_totals, view_for
import plan_launcher as workflow
from plan_launcher import execute as execute_session
from tests.support.terminal_screen import Terminal


@pytest.fixture(autouse=True)
def synthetic_plan_evidence(monkeypatch):
    # Driver fixtures have synthetic acceptance strings. Real publication,
    # rotation and interruption are qualified by test_plan_evidence.
    monkeypatch.setattr(workflow.plan_evidence, 'capture', lambda *_: None)
    monkeypatch.setattr(workflow.plan_evidence, 'carry', lambda *_: None)
    monkeypatch.setattr(workflow.plan_evidence, 'preserve', lambda *_: None)
    monkeypatch.setattr(workflow.plan_evidence, 'recover', lambda *_: None)
    monkeypatch.setattr(workflow.plan_evidence, 'rewrite_references', lambda *_: None)


@pytest.fixture(params=[
    ('reliability-plan', 'docs/Reliability-Plan.md'),
    ('kiosk-prompt', 'docs/Kiosk-Session-Confinement-Plan.md'),
], ids=['reliability-plan', 'kiosk-prompt'])
def plan_adapter(monkeypatch, request):
    name, plan = request.param
    entry = Path(workflow.__file__).with_name(name)

    def invoke(*args):
        monkeypatch.setattr(sys, 'argv', [str(entry), *args])
        # The public entry point adds its tools directory to the import path.
        monkeypatch.syspath_prepend(str(entry.parent))
        with pytest.raises(SystemExit) as result:
            runpy.run_path(str(entry), run_name='__main__')
        return result.value.code

    return invoke, workflow.PlanWorkflow(
        name=name, plan=plan, model='gpt-6.1-sol', effort='high', vm=True)


def test_plan_adapter_inherits_shared_commit_and_push_policy(plan_adapter, monkeypatch):
    invoke, spec = plan_adapter
    calls = []
    monkeypatch.setattr(workflow, 'main', lambda spec: calls.append(spec) or 7)
    assert invoke() == 7
    assert calls == [spec]
    assert calls[0].commit_prefix == 'TA' and calls[0].push is True
    assert workflow.PlanWorkflow('execute-plan').commit_prefix == 'TA'
    assert workflow.PlanWorkflow('execute-plan').push is True


def test_plan_adapter_default_check_has_no_execution_side_effects(
        rig, plan_adapter, monkeypatch, capsys):
    import vm_selection

    invoke, spec = plan_adapter
    master = rig.root / spec.plan
    master.parent.mkdir(parents=True, exist_ok=True)
    for name in ('queue.md', '001.md', '002.md'):
        source, destination = rig.root / 'docs' / name, master.parent / name
        if source != destination:
            shutil.copy2(source, destination)
    master.write_text('Task queue: [Queue](queue.md).\nNext task: **001 — First**.\n')
    monkeypatch.setattr(workflow, '__file__', str(rig.root / 'tools/plan_launcher.py'))

    def unexpected(*_args, **_kwargs):
        pytest.fail('--check attempted VM selection, a model/process launch or Git changes')

    monkeypatch.setattr(vm_selection, 'execution_selection', unexpected)
    monkeypatch.setattr(workflow.launcher, 'select', unexpected)
    monkeypatch.setattr(workflow.subprocess, 'Popen', unexpected)
    monkeypatch.setattr(workflow, 'git_output', unexpected)
    assert invoke('--check') == 0
    assert json.loads(capsys.readouterr().out) == dict(
        plan=spec.plan, queue=str((master.parent / 'queue.md').relative_to(rig.root)),
        next_task='001', remaining=2,
        model='gpt-6.1-sol', effort='high',
    )


@pytest.mark.parametrize('action', ['limit', 'stop'])
def test_plan_adapter_shares_master_ownership_and_common_controls(
        rig, plan_adapter, monkeypatch, action):
    import vm_selection

    invoke, _spec = plan_adapter
    selections = []
    monkeypatch.setattr(workflow, '__file__', str(rig.root / 'tools/plan_launcher.py'))
    monkeypatch.setattr(vm_selection, 'execution_selection', lambda selector: selections.append(selector))
    monkeypatch.setattr(vm_selection, 'execution_binding', lambda: None)
    monkeypatch.setattr(workflow.launcher, 'follow', lambda *_args, **_kwargs: 0)
    if action == 'stop':
        (rig.root / rig.plan.path).write_text('Interrupted master edit\n')

    def select(root, name, command, **options):
        assert root == rig.root and name == 'plans'
        assert options['namespace'] == rig.plan.namespace
        assert options['stop'] == (action == 'stop')
        assert options['stop_marker'] == 'stop'
        options['on_attach'](rig.run)
        return rig.run, False

    monkeypatch.setattr(workflow.launcher, 'select', select)
    controls = ['--stop'] if action == 'stop' else ['--tasks', '0']
    assert invoke('--plan', rig.plan.path, *controls) == 0
    assert selections == ([] if action == 'stop' else [None])
    assert TaskBudget(rig.run).read()['tasks'] == (1 if action == 'stop' else None)


def prepare(root, count=2):
    docs = root / 'docs'
    docs.mkdir(parents=True, exist_ok=True)
    (docs / 'plan.md').write_text('Task queue: [Queue](queue.md).\nNext task: **001 — First**.\n')
    rows = ['| Done | ID | Task | Requires | Scope |', '| --- | --- | --- | --- | --- |']
    for number in range(1, count + 1):
        identity = f'{number:03}'
        (docs / f'{identity}.md').write_text(f'# Task {identity}\nAcceptance: host\n')
        rows.append(f'| [ ] | {identity} | [Task {identity}]({identity}.md) | — | finite scope {identity} |')
    rows += ['## Deferred future work', '| [ ] | later | No brief | unknown | deferred |']
    (docs / 'queue.md').write_text('\n'.join(rows) + '\n')
    return Plan.load(root, 'docs/plan.md')


def complete(plan, identity):
    queue = plan.root / plan.queue
    queue.write_text(queue.read_text().replace(f'| [ ] | {identity} |', f'| [x] | {identity} |'))
    active = queue.read_text().split('## Deferred future work')[0]
    next_id = next((line.split('|')[2].strip() for line in active.splitlines()
                    if line.startswith('| [ ] |')), None)
    pointer = f'Next task: **{next_id} — Next**.' if next_id else 'Next task: none.'
    (plan.root / plan.path).write_text('Task queue: [Queue](queue.md).\n' + pointer + '\n')


def state_for(plan, **changes):
    task = plan.next_task()
    record = workflow.task_record(task)
    state = dict(record, task=record, phase='implement', task_sessions=0,
                 total_sessions=0, session_limit=5,
                 stage_baseline={}, protected_staged=[], queue_before=plan.state(),
                 queue_structure=plan.structure(selected=task.id), in_flight=False)
    state.update(changes)
    return state


def response(state, status='task_complete'):
    return dict(status=status, task_id=state['task_id'], summary='Verified finite task.',
                handoff='Continue from the retained checkpoint.', cleanup_complete=True,
                stage_paths=['docs/plan.md', 'docs/queue.md'], blocker=None,
                checks=[dict(kind='host', target='', result='passed', evidence='Private scoped check passed.')])


@pytest.fixture
def rig(tmp_path, monkeypatch):
    plan = prepare(tmp_path)
    run = tmp_path / 'run'
    run.mkdir()
    TaskBudget(run).initialize(1)
    monkeypatch.setattr(workflow.signal, 'signal', lambda *_: None)
    cleanups = []
    monkeypatch.setattr(workflow.launcher, 'finish_nested', lambda root, selected: cleanups.append(selected))
    monkeypatch.setattr(workflow, 'worktree_snapshot', lambda _: {})
    monkeypatch.setattr(workflow, 'git_output', lambda *_args, **_kwargs: SimpleNamespace(stdout='', stderr='', returncode=0))
    monkeypatch.setattr(workflow, 'stage_task', lambda root, paths, **kwargs: paths)
    monkeypatch.setattr(workflow, 'finish_commit', lambda *_args: None)
    monkeypatch.setattr(workflow, 'pull_before_commit', lambda *_args, **_kwargs: None)
    spec = workflow.PlanWorkflow('fixture-plan', plan.path, effort='xhigh')
    calls = []

    def execute(root, selected_spec, selected_run, owner):
        state = json.loads((selected_run / 'checkpoint.json').read_text())
        calls.append((state['task_id'], state['task_sessions'], selected_spec.effort))
        complete(plan, state['task_id'])
        return response(state)

    monkeypatch.setattr(workflow, 'execute', execute)

    def worker(state=None):
        owner = os.open(run / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
        status = workflow.worker(tmp_path, run, owner, spec,
                                 state or dict(phase='complete', task_sessions=0, total_sessions=0))
        with pytest.raises(OSError):
            os.fstat(owner)
        return status

    return SimpleNamespace(root=tmp_path, plan=plan, run=run, spec=spec, calls=calls,
                           worker=worker, cleanups=cleanups)


def test_plan_selects_first_unfinished_and_excludes_deferred_rows(tmp_path):
    plan = prepare(tmp_path)
    assert [task.id for task in plan.tasks()] == ['001', '002']
    assert plan.next_task().id == '001'
    complete(plan, '001')
    assert plan.next_task().id == '002'
    complete(plan, '002')
    assert plan.next_task() is None
    assert plan.namespace == Plan.load(tmp_path, plan.path).namespace


@pytest.mark.parametrize('payload', [None, '', 'not JSON', '{', '\udcff'])
def test_shared_response_reader_classifies_only_missing_or_malformed_result(tmp_path, payload):
    from launcher_runtime import SessionResultRejected, read_session_result
    if payload is not None:
        (tmp_path / 'agent-result.json').write_bytes(payload.encode('utf-8', errors='surrogateescape'))
    with pytest.raises(SessionResultRejected, match='missing or invalid JSON'):
        read_session_result(tmp_path)


@pytest.mark.parametrize('failure', [OSError('ownership refused'), PermissionError('missing grant')])
def test_shared_response_gate_does_not_retry_infrastructure_failures(failure):
    from launcher_runtime import validate_session_result
    def validate(_):
        raise failure
    with pytest.raises(type(failure), match=str(failure)):
        validate_session_result({}, validate)


def insert_unlinked_prerequisite(plan, consumer):
    queue = plan.root / plan.queue
    queue.write_text(queue.read_text().replace(f'| [ ] | {consumer} |',
        '| [ ] | pre | [Prerequisite](pre.md) | Baseline | Needed shared fixture |\n'
        f'| [ ] | {consumer} |'))
    (plan.root / 'docs/pre.md').write_text('Acceptance: host\n')
    (plan.root / plan.path).write_text('Task queue: [Queue](queue.md).\nNext task: **pre — Prerequisite**.\n')


def test_rejected_prerequisite_returns_to_same_coordinator_before_advancing(rig, monkeypatch):
    original = rig.plan.state()
    calls = []
    accepted = workflow.execute
    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        calls.append(state['task_id'])
        if len(calls) == 1:
            insert_unlinked_prerequisite(rig.plan, '001')
            return response(state, 'prerequisite_required')
        if len(calls) == 2:
            assert state['task_id'] == '001' and state['task_sessions'] == 2
            assert state['queue_before'] == original
            assert 'prerequisite handoff' in (run / 'prompt.txt').read_text()
            assert 'Requires chain' in (run / 'prompt.txt').read_text()
            assert TaskBudget(run).read()['completed'] == 0
            queue = root / rig.plan.queue
            queue.write_text(queue.read_text().replace('| — | finite scope 001', '| pre | finite scope 001'))
            return response(state, 'prerequisite_required')
        return accepted(root, spec, run, owner)
    monkeypatch.setattr(workflow, 'execute', execute)
    assert rig.worker() == 0
    assert calls == ['001', '001', 'pre']
    assert rig.plan.state() == {'pre': True, '001': False, '002': False}
    state = json.loads((rig.run / 'checkpoint.json').read_text())
    assert state['suspended_tasks']['001']['task_sessions'] == 2
    assert 'result_recovery' not in state['suspended_tasks']['001']
    assert json.loads((rig.run / 'rejected-agent-result.json').read_text())['status'] == 'prerequisite_required'
    assert TaskBudget(rig.run).read()['completed'] == 1


def test_rejected_result_retries_are_bounded_and_retain_original_baseline(rig, monkeypatch):
    original = rig.plan.state()
    attempts = []
    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        attempts.append(state['task_sessions'])
        assert state['queue_before'] == original
        return response(state)  # No acceptance/queue close-out was performed.
    monkeypatch.setattr(workflow, 'execute', execute)
    monkeypatch.setattr(workflow, 'closeout', lambda *_: pytest.fail('rejected completion reached Git'))
    assert rig.worker() == 1
    assert attempts == [1, 2, 3, 4, 5]
    state = json.loads((rig.run / 'checkpoint.json').read_text())
    assert state['reason'].startswith('task session limit reached')
    assert 'only the selected task' in state['result_recovery']['reason']
    assert state['queue_before'] == original and rig.plan.state() == original
    assert 'controller rejected' in (rig.run / 'handoff.txt').read_text()
    assert TaskBudget(rig.run).read()['completed'] == 0


def test_rejected_result_stops_before_retrying_with_stale_validation_code(rig, monkeypatch):
    attempts = []
    sources = {'execution_plan.py': 'original'}
    monkeypatch.setattr(workflow, 'response_validator_sources', lambda: sources.copy())

    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        attempts.append(state['task_sessions'])
        sources['execution_plan.py'] = 'repaired'
        return response(state)  # The running controller still rejects it.

    monkeypatch.setattr(workflow, 'execute', execute)
    monkeypatch.setattr(workflow, 'closeout', lambda *_: pytest.fail('rejected completion reached Git'))
    original = rig.plan.state()
    assert rig.worker() == 1
    assert attempts == [1]
    state = json.loads((rig.run / 'checkpoint.json').read_text())
    assert 'validation code changed' in state['reason']
    assert 'fresh run' in state['reason'] and 'session limit reached' not in state['reason']
    assert state['task_sessions'] == 1 and state['session_limit'] == 5
    assert state['queue_before'] == original and rig.plan.state() == original
    assert state['result_recovery']['reason']
    assert json.loads((rig.run / 'rejected-agent-result.json').read_text()) == response(state)
    assert rig.cleanups == [rig.run, rig.run]
    assert TaskBudget(rig.run).read()['completed'] == 0


@pytest.mark.parametrize('status', ['continue', 'blocked', 'task_complete'])
def test_valid_result_source_change_stops_before_next_admission_or_blocked_wait(rig, monkeypatch, status):
    original = rig.plan.state()
    sources = {'plan_evidence_recovery.py': 'original'}
    attempts, admissions = [], []
    admit = TaskBudget.admit
    monkeypatch.setattr(workflow, 'response_validator_sources', lambda: sources.copy())

    def record_admission(budget):
        admissions.append(budget.run)
        return admit(budget)

    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        attempts.append(state['task_sessions'])
        sources['plan_evidence_recovery.py'] = 'repaired'
        result = response(state, status)
        if status == 'task_complete':
            complete(rig.plan, state['task_id'])
        elif status == 'blocked':
            result['blocker'] = dict(explanation='Required authority is unavailable.',
                question='Which route is authorized?', options=['Keep the boundary.', 'Authorize the route.'])
        workflow.launcher.atomic(run / 'agent-result.json', result)
        return result

    monkeypatch.setattr(TaskBudget, 'admit', record_admission)
    monkeypatch.setattr(workflow, 'execute', execute)
    monkeypatch.setattr(workflow, 'wait_for_answer',
                        lambda *_args, **_kwargs: pytest.fail('stale controller waited for an answer'))
    assert rig.worker() == 1
    assert attempts == [1] and admissions == [rig.run]
    state = json.loads((rig.run / 'checkpoint.json').read_text())
    assert 'validation code changed' in state['reason'] and 'fresh run' in state['reason']
    assert state['task_id'] == '001' and state['task_sessions'] == state['total_sessions'] == 1
    assert state['queue_before'] == original and not state['in_flight']
    assert 'result_recovery' not in state
    assert state['phase'] == {'continue': 'recover', 'blocked': 'blocked', 'task_complete': 'complete'}[status]
    assert json.loads((rig.run / 'agent-result.json').read_text())['status'] == status
    assert 'fresh run' in (rig.run / 'handoff.txt').read_text()
    assert rig.plan.state() == dict(original, **{'001': status == 'task_complete'})
    assert TaskBudget(rig.run).read()['completed'] == int(status == 'task_complete')
    assert rig.cleanups[-1] == rig.run


def test_valid_continuation_source_change_reaches_fresh_startup_recovery(rig, monkeypatch):
    sources = {'plan_evidence_recovery.py': 'original'}
    accepted_execute = workflow.execute
    attempts, recovered = [], []
    monkeypatch.setattr(workflow, 'response_validator_sources', lambda: sources.copy())

    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        attempts.append(state['task_sessions'])
        sources['plan_evidence_recovery.py'] = 'repaired'
        result = response(state, 'continue')
        workflow.launcher.atomic(run / 'agent-result.json', result)
        return result

    monkeypatch.setattr(workflow, 'execute', execute)
    assert rig.worker() == 1
    retained = (rig.run / 'checkpoint.json').read_bytes()

    def recover(plan, state, previous, **callbacks):
        assert previous == rig.run and not state['in_flight']
        assert state['task_sessions'] == state['total_sessions'] == 1
        assert callbacks['verify_proof'] and callbacks['read_authorization']
        recovered.append(state['task_id'])
        return state

    monkeypatch.setattr(workflow.plan_evidence_recovery, 'recover_evidence', recover)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    initial = workflow.initial_state(rig.plan, rig.spec, rig.run.parent)
    assert recovered == ['001'] and attempts == [1]
    assert initial['session_limit'] == 1 + rig.spec.max_sessions
    assert (rig.run / 'checkpoint.json').read_bytes() == retained
    restarted = rig.root / 'restarted'
    restarted.mkdir()
    TaskBudget(restarted).initialize(1)
    monkeypatch.setattr(workflow, 'execute', accepted_execute)
    owner = os.open(restarted / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
    assert workflow.worker(rig.root, restarted, owner, rig.spec, initial) == 0
    with pytest.raises(OSError):
        os.fstat(owner)
    assert rig.calls == [('001', 2, rig.spec.effort)]
    assert TaskBudget(restarted).read()['completed'] == 1


def test_source_change_while_blocked_retains_answer_before_new_session(rig, monkeypatch):
    sources = {'plan_launcher.py': 'original'}
    monkeypatch.setattr(workflow, 'response_validator_sources', lambda: sources.copy())
    blocker = dict(explanation='Required authority is unavailable.', question='Which route is authorized?',
                   options=['Keep the boundary.', 'Authorize the route.'])
    answer = {'question': blocker['question'], 'answer': blocker['options'][0]}

    def wait(*_args, **_kwargs):
        sources['plan_launcher.py'] = 'repaired'
        return answer

    monkeypatch.setattr(workflow, 'wait_for_answer', wait)
    monkeypatch.setattr(TaskBudget, 'admit', lambda *_: pytest.fail('stale controller admitted a session'))
    state = state_for(rig.plan, phase='blocked', task_sessions=1, total_sessions=1,
                      blocker=blocker, blocker_id='decision')
    assert rig.worker(state) == 1
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    assert checkpoint['phase'] == 'recover' and checkpoint['answer'] == answer
    assert checkpoint['task_sessions'] == checkpoint['total_sessions'] == 1
    assert 'fresh run' in checkpoint['reason']
    assert rig.calls == [] and rig.cleanups == [rig.run]
    assert TaskBudget(rig.run).read()['completed'] == 0


def write_evidence_recovery_request(plan, state):
    recovery = workflow.plan_evidence_recovery
    request = dict(version=1, plan=plan.path, queue=plan.queue, task=state['task'],
                   baseline_sha256=recovery.protected_digest(state),
                   queue_sha256=recovery.digest((plan.root / plan.queue).read_bytes()),
                   authorization={}, corrections=[])
    # Boundary detection parses request identity only. Authorization and proof
    # validation must remain exclusively with the inactive startup controller.
    Path(state['task']['brief']).write_text('Acceptance: host\n```plan-evidence-recovery\n'
        + json.dumps(request) + '\n```\n')
    return request


@pytest.mark.parametrize('status', ['continue', 'blocked'])
def test_new_evidence_request_stops_after_one_valid_session_without_source_changes(rig, monkeypatch, status):
    original = rig.plan.state()
    attempts = []
    monkeypatch.setattr(workflow, 'response_validator_sources', lambda: {'unchanged': 'source'})

    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        attempts.append(state['task_sessions'])
        write_evidence_recovery_request(rig.plan, state)
        result = response(state, status)
        if status == 'blocked':
            result['blocker'] = dict(explanation='Required authority is unavailable.',
                question='Which route is authorized?', options=['Keep the boundary.', 'Authorize the route.'])
        workflow.launcher.atomic(run / 'agent-result.json', result)
        return result

    monkeypatch.setattr(workflow, 'execute', execute)
    monkeypatch.setattr(workflow, 'wait_for_answer',
                        lambda *_args, **_kwargs: pytest.fail('pending recovery reached blocked wait'))
    monkeypatch.setattr(workflow.plan_evidence_recovery, 'recover_evidence',
                        lambda *_args, **_kwargs: pytest.fail('active worker applied evidence recovery'))
    assert rig.worker() == 1
    assert attempts == [1]
    state = json.loads((rig.run / 'checkpoint.json').read_text())
    assert state['task_id'] == '001' and state['task_sessions'] == state['total_sessions'] == 1
    assert state['queue_before'] == original and rig.plan.state() == original
    assert not state['in_flight'] and 'evidence_recovery' not in state
    assert 'unapplied evidence recovery request' in state['reason']
    assert 'fresh run' in (rig.run / 'handoff.txt').read_text()
    assert json.loads((rig.run / 'agent-result.json').read_text())['status'] == status
    assert TaskBudget(rig.run).read()['completed'] == 0 and rig.cleanups == [rig.run]


@pytest.mark.parametrize('new_selection', [False, True])
def test_prepared_evidence_request_stops_before_first_session_including_new_selection(rig, monkeypatch, new_selection):
    state = state_for(rig.plan)
    write_evidence_recovery_request(rig.plan, state)
    if new_selection:
        state = dict(phase='complete', task_sessions=0, total_sessions=0)
    monkeypatch.setattr(workflow, 'execute',
                        lambda *_: pytest.fail('pending recovery started an agent session'))
    assert rig.worker(state) == 1
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    assert checkpoint['task_id'] == '001' and checkpoint['task_sessions'] == checkpoint['total_sessions'] == 0
    assert 'unapplied evidence recovery request' in checkpoint['reason']
    assert TaskBudget(rig.run).read()['completed'] == 0


@pytest.mark.parametrize('exact_marker', [False, True])
def test_evidence_request_boundary_matches_exact_applied_request_identity(rig, exact_marker):
    state = state_for(rig.plan)
    request = write_evidence_recovery_request(rig.plan, state)
    recovery = workflow.plan_evidence_recovery
    # Full transaction verification belongs to startup and has its own tests;
    # this fixture supplies the applied identity returned by that verified route.
    state['evidence_recovery'] = dict(request_sha256=
        recovery.digest(recovery.encoded(request)) if exact_marker else 'another request')
    assert rig.worker(state) == (0 if exact_marker else 1)
    assert rig.calls == ([('001', 1, rig.spec.effort)] if exact_marker else [])
    assert TaskBudget(rig.run).read()['completed'] == int(exact_marker)


@pytest.mark.parametrize('changed', [
    'plan_launcher.py', 'execution_plan.py', 'document_checks.py', 'launcher_runtime.py',
    'plan_evidence.py', 'plan_evidence_recovery.py', 'evidence_bundle.py', 'detached_launcher.py',
])
def test_response_validator_sources_detects_content_changes_only(tmp_path, monkeypatch, changed):
    names = ('plan_launcher.py', 'execution_plan.py', 'document_checks.py', 'launcher_runtime.py',
             'plan_evidence.py', 'plan_evidence_recovery.py', 'evidence_bundle.py', 'detached_launcher.py')
    for name in names:
        (tmp_path / name).write_text('original')
    monkeypatch.setattr(workflow, '__file__', str(tmp_path / 'plan_launcher.py'))
    original = workflow.response_validator_sources()
    (tmp_path / changed).write_text('original')
    assert workflow.response_validator_sources() == original
    (tmp_path / changed).write_text('repaired')
    current = workflow.response_validator_sources()
    assert {name for name in names if current[name] != original[name]} == {changed}


@pytest.mark.parametrize('legacy', [False, True])
def test_rejected_handoff_resumes_after_stop_with_unchanged_task_and_guards(rig, monkeypatch, legacy):
    state = state_for(rig.plan, in_flight=True, task_sessions=1)
    insert_unlinked_prerequisite(rig.plan, '001')
    result = response(state, 'prerequisite_required')
    (rig.run / 'agent-result.json').write_text(json.dumps(result))
    if legacy:
        state['reason'] = 'prerequisite handoff needs a valid backward dependency insertion and owned cleanup'
    else:
        from launcher_runtime import SessionResultRejected, retain_result_rejection
        state.update(phase='recover', in_flight=False, plan_queue=rig.plan.queue,
                     result_recovery=retain_result_rejection(rig.run,
                         SessionResultRejected('unlinked prerequisite', result), label='fixture'))
    workflow.launcher.atomic(rig.run / 'checkpoint.json', state)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    restored = workflow.initial_state(rig.plan, rig.spec, rig.run.parent)
    assert restored['task_id'] == '001' and restored['queue_before'] == state['queue_before']
    assert restored['result_recovery']['reason']
    assert restored['session_limit'] == 6
    assert workflow.load_plan(rig.root, rig.plan.path, restored) == rig.plan
    (rig.run / 'stop').touch()
    assert rig.worker(restored) == 0
    assert not rig.calls and TaskBudget(rig.run).read()['completed'] == 0
    assert 'controller rejected' in (rig.run / 'handoff.txt').read_text()


@pytest.mark.parametrize('adapter', ['ordinary-plan', 'write-e2e'])
def test_interrupted_rejection_retention_resumes_exact_response_and_original_task(rig, monkeypatch, adapter):
    from launcher_runtime import SessionResultRejected, retain_result_rejection
    import write_e2e

    state = state_for(rig.plan, phase='recover', in_flight=False, task_sessions=1,
                      plan_queue=rig.plan.queue)
    source = rig.run / 'agent-result.json'
    source.write_text('{"latest": "rejected response"}')
    (rig.run / 'rejected-agent-result.json').write_text('stale preceding response')
    read_bytes = Path.read_bytes
    def interrupted(path):
        if path == source:
            raise OSError('interrupted while retaining rejected response')
        return read_bytes(path)
    monkeypatch.setattr(Path, 'read_bytes', interrupted)
    with pytest.raises(OSError, match='interrupted while retaining'):
        retain_result_rejection(rig.run, SessionResultRejected('latest guard failure'),
                                label='fixture', checkpoint=state)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    restored = (workflow.initial_state(rig.plan, rig.spec, rig.run.parent)
                if adapter == 'ordinary-plan' else write_e2e.initial_state(rig.root, rig.run.parent))
    assert restored['task_id'] == '001' and restored['queue_before'] == state['queue_before']
    rejection = restored['result_recovery']
    assert rejection['reason'] == 'latest guard failure'
    assert Path(rejection['response']).read_text() == '{"latest": "rejected response"}'
    assert Path(rejection['response']) != rig.run / 'rejected-agent-result.json'


def test_legacy_malformed_response_resumes_only_matching_retained_decode_failure(rig, monkeypatch):
    state = state_for(rig.plan, in_flight=True, task_sessions=1)
    try:
        json.loads('malformed result')
    except ValueError as error:
        state['reason'] = str(error)
    (rig.run / 'agent-result.json').write_text('malformed result')
    workflow.launcher.atomic(rig.run / 'checkpoint.json', state)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    restored = workflow.initial_state(rig.plan, rig.spec, rig.run.parent)
    assert restored['result_recovery']['reason'].startswith('agent response is missing or invalid JSON')
    assert not restored['in_flight'] and restored['session_limit'] == 6


@pytest.mark.parametrize('provider_error', [True, False])
def test_failed_agent_preserves_current_reason_and_unfinished_task(rig, monkeypatch, provider_error):
    reason = 'Codex turn failed (cyberPolicy): Provider rejected the turn.'
    error_path = rig.run / 'agent-error.json'
    error_path.write_text(json.dumps({'message': 'Stale failure from a previous session.'}))
    launches = []

    class FailedSupervisor:
        def __enter__(self):
            assert not error_path.exists()
            launches.append(True)
            if provider_error:
                error_path.write_text(json.dumps({'message': reason}))
            return self

        def wait(self):
            return 1

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(workflow.subprocess, 'Popen', lambda *_args, **_kwargs: FailedSupervisor())
    monkeypatch.setattr(workflow.launcher, 'compact_log', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workflow, 'execute', execute_session)
    assert rig.worker() == 1
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    expected = reason if provider_error else 'agent session exited 1; inspect retained output and handoff'
    assert checkpoint['reason'] == expected
    assert expected in (rig.run / 'handoff.txt').read_text()
    assert checkpoint['in_flight'] and checkpoint['task_sessions'] == 1
    assert rig.plan.next_task().id == '001'
    assert json.loads((rig.run / 'result.json').read_text()) == dict(status=1, tasks=0)
    assert launches == [True] and rig.cleanups == [rig.run]


@pytest.mark.parametrize('defect, message', [
    ('duplicate', 'duplicate task IDs'), ('pointer', 'pointer must name'),
    ('later-dependency', 'unknown or later task'), ('unknown-dependency', 'unknown or later task'),
    ('missing-brief', 'regular checkout Markdown'),
])
def test_plan_rejects_ambiguous_selection(tmp_path, defect, message):
    plan = prepare(tmp_path)
    queue = tmp_path / plan.queue
    text = queue.read_text()
    if defect == 'duplicate':
        queue.write_text(text.replace('| 002 |', '| 001 |'))
    elif defect == 'pointer':
        (tmp_path / plan.path).write_text('Task queue: [Queue](queue.md).\nNext task: **002 — Wrong**.\n')
    elif defect.endswith('dependency'):
        queue.write_text(text.replace('| — | finite scope 001', f'| {"002" if defect == "later-dependency" else "unknown"} | finite scope 001'))
    else:
        (tmp_path / 'docs/001.md').unlink()
    with pytest.raises(ValueError, match=message):
        plan.tasks()


@pytest.mark.parametrize('path', ['../outside.md', '/outside.md', 'docs/plan.txt', 'docs/linked.md'])
def test_plan_paths_refuse_escape_nonmarkdown_and_symlinks(tmp_path, path):
    prepare(tmp_path)
    (tmp_path / 'docs/linked.md').symlink_to(tmp_path / 'docs/plan.md')
    with pytest.raises(ValueError, match='regular checkout Markdown'):
        local_file(tmp_path, path)


def test_transition_preserves_other_row_scope_and_dependency(tmp_path):
    plan = prepare(tmp_path)
    before, structure = plan.state(), plan.structure(selected='001')
    queue = tmp_path / plan.queue
    queue.write_text(queue.read_text().replace('finite scope 002', 'changed scope'))
    with pytest.raises(ValueError, match='scope or prerequisites changed'):
        plan.validate_transition(before, '001', complete=False, structure=structure)


def test_completed_prerequisite_selects_its_consumer(tmp_path):
    plan = prepare(tmp_path)
    queue = tmp_path / plan.queue
    queue.write_text(queue.read_text().replace('| — | finite scope 002', '| 001 | finite scope 002'))
    complete(plan, '001')
    assert plan.next_task().id == '002'
    assert plan.next_task().requires == ('001',)


@pytest.mark.parametrize('defect', ['missing-target', 'host-substitution', 'failed', 'no-evidence', 'unfinished-cleanup'])
def test_installed_completion_requires_each_named_target_and_cleanup(rig, defect):
    (rig.root / 'docs/001.md').write_text('Acceptance: installed\nTargets: target-one, target-two\n')
    state = state_for(rig.plan)
    result = response(state)
    result['checks'] = [dict(kind='installed', target=target, result='passed', evidence=f'Retained {target} result.')
                        for target in state['task']['targets']]
    if defect == 'missing-target':
        result['checks'].pop()
    elif defect == 'host-substitution':
        result['checks'][1]['kind'] = 'host'
    elif defect == 'failed':
        result['checks'][1]['result'] = 'failed'
    elif defect == 'no-evidence':
        result['checks'][1]['evidence'] = ' '
    else:
        result['cleanup_complete'] = False
    complete(rig.plan, '001')
    with pytest.raises(ValueError, match='passing scoped acceptance evidence and owned cleanup'):
        workflow.validate_result(rig.plan, state, result)


@pytest.mark.parametrize('kind', ['host', 'review', 'reconciliation'])
def test_noninstalled_acceptance_keeps_declared_target_scope(rig, kind):
    (rig.root / 'docs/001.md').write_text(f'Acceptance: {kind}\nTargets: target-one, target-two\n')
    state = state_for(rig.plan)
    prompt = workflow.session_prompt(rig.plan, rig.spec, state)
    assert 'empty only when the\nbrief declares no Targets' in prompt
    assert 'empty for host/review' not in prompt
    result = response(state)
    result['checks'] = [dict(kind=kind, target=target, result='passed', evidence=f'Reviewed {target}.')
                        for target in state['task']['targets']]
    complete(rig.plan, '001')
    workflow.validate_result(rig.plan, state, result)
    result['checks'].pop()
    with pytest.raises(ValueError, match='passing scoped acceptance evidence'):
        workflow.validate_result(rig.plan, state, result)


@pytest.mark.parametrize('limit', [0, -1, -100, None])
def test_nonpositive_budgets_are_unlimited(tmp_path, limit):
    budget = TaskBudget(tmp_path)
    budget.initialize(limit)
    for _ in range(4):
        assert budget.admit()
        budget.complete()
    assert task_limit(limit) is None
    assert budget.read()['completed'] == 4


@pytest.mark.parametrize('limit', [0, -1, 3])
def test_task_counter_uses_numeric_remaining_total_and_live_limits(tmp_path, limit):
    budget = TaskBudget(tmp_path)
    budget.initialize(limit, remaining=5)
    steps = [dict(key='current', lines=['Current task'])]
    total = 3 if limit > 0 else 5
    assert task_progress(tmp_path, steps)[0]['lines'] == [f'Tasks: 0/{total}/{total}']
    assert budget.admit()
    assert task_progress(tmp_path, steps)[0]['lines'] == [f'Tasks: 0/{total}/{total}']
    budget.complete()
    assert task_progress(tmp_path, steps)[0]['lines'] == [f'Tasks: 1/{total - 1}/{total}']
    budget.set_limit(0)
    assert task_progress(tmp_path, steps)[0]['lines'] == ['Tasks: 1/4/5']
    assert task_progress(tmp_path, steps)[1:] == steps


@pytest.mark.parametrize('already_complete', [False, True])
def test_unlimited_plan_counter_excludes_previously_completed_tasks(rig, monkeypatch, already_complete):
    if already_complete:
        complete(rig.plan, '001')
    TaskBudget(rig.run).initialize(0)
    counters = []

    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        counters.append(task_progress(run, [])[0]['lines'][0])
        complete(rig.plan, state['task_id'])
        return response(state)

    monkeypatch.setattr(workflow, 'execute', execute)
    assert rig.worker() == 0
    assert counters == (['Tasks: 0/1/1'] if already_complete else ['Tasks: 0/2/2', 'Tasks: 1/1/2'])
    assert task_progress(rig.run, [])[0]['lines'] == [
        'Tasks: 1/0/1' if already_complete else 'Tasks: 2/0/2']


def test_active_budget_replacement_and_closed_refusal(tmp_path):
    budget = TaskBudget(tmp_path)
    budget.initialize(1)
    assert budget.admit()
    budget.complete()
    assert budget.set_limit(3) == 3
    assert budget.admit()
    assert budget.set_limit(-3) is None
    assert budget.admit()
    budget.close()
    with pytest.raises(ValueError, match='finishing'):
        budget.set_limit(4)
    assert not budget.admit()


def test_budget_serializes_concurrent_completions(tmp_path):
    budget = TaskBudget(tmp_path)
    budget.initialize(0)
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(lambda _: budget.complete(), range(24)))
    assert budget.read()['completed'] == 24


def test_oversized_budget_warns_and_queue_exhausts_naturally(rig, capsys):
    warn_remaining(8, 2, label=rig.spec.name)
    TaskBudget(rig.run).initialize(8)
    assert rig.worker() == 0
    assert [call[0] for call in rig.calls] == ['001', '002']
    assert json.loads((rig.run / 'result.json').read_text()) == dict(status=0, tasks=2)
    assert 'only 2 remain' in capsys.readouterr().out
    assert 'queue complete' in (rig.run / 'handoff.txt').read_text()


def test_task_limit_stops_before_next_task(rig):
    assert rig.worker() == 0
    assert [call[0] for call in rig.calls] == ['001']
    assert rig.plan.next_task().id == '002'
    assert 'task limit reached' in (rig.run / 'handoff.txt').read_text()


@pytest.mark.parametrize('elapsed, duration', [(720, '12m'), (3600, '1h 0m'), (4320, '1h 12m')])
def test_followup_sessions_do_not_consume_completed_task_budget(rig, monkeypatch, elapsed, duration):
    from launcher_progress import read_progress
    from rich.console import Console
    from rich.text import Text
    clock = [1000.0]
    monkeypatch.setattr(workflow, 'time', SimpleNamespace(time=lambda: clock[0]))

    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        rig.calls.append((state['task_id'], state['task_sessions'], spec.effort))
        clock[0] += elapsed / 3
        if state['task_sessions'] < 3:
            return response(state, 'continue')
        complete(rig.plan, state['task_id'])
        return response(state)
    monkeypatch.setattr(workflow, 'execute', execute)
    assert rig.worker() == 0
    assert rig.calls == [('001', 1, 'xhigh'), ('001', 2, 'xhigh'), ('001', 3, 'xhigh')]
    assert TaskBudget(rig.run).read()['completed'] == 1
    summary = Text.from_ansi(read_progress(rig.run)[-1]['lines'][0])
    assert summary.plain == f'✓ Task 001: Task 001 ({duration})'
    assert all(summary.get_style_at_offset(Console(), offset).color.number == 2
               for offset in range(len(summary.plain)))


def test_session_cap_retains_fixed_effort_and_unfinished_task(rig, monkeypatch):
    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        rig.calls.append((state['task_id'], state['task_sessions'], spec.effort))
        return response(state, 'continue')
    monkeypatch.setattr(workflow, 'execute', execute)
    assert rig.worker() == 1
    assert rig.calls == [('001', n, 'xhigh') for n in range(1, 6)]
    assert rig.plan.next_task().id == '001'
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    assert checkpoint['phase'] == 'recover'
    assert 'session limit' in checkpoint['reason']


def test_stop_while_blocked_preserves_unanswered_question(rig, monkeypatch):
    blocker = dict(explanation='Required authority is unavailable.', question='Which route is authorized?',
                   options=['Keep the current boundary.', 'Authorize the proposed route.'])
    state = state_for(rig.plan, phase='blocked', blocker=blocker, blocker_id='decision')
    def stop(run, *_args, **_kwargs):
        workflow.launcher.atomic(run / 'question.json', dict(blocker, id='decision', answer=None))
        (run / 'stop').touch()
        return None
    monkeypatch.setattr(workflow, 'wait_for_answer', stop)
    assert rig.worker(state) == 0
    assert rig.calls == []
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    assert checkpoint['phase'] == 'blocked' and checkpoint['blocker_id'] == 'decision'
    assert json.loads((rig.run / 'question.json').read_text())['answer'] is None


def test_cancellation_retains_inflight_task_and_runs_owned_cleanup(rig, monkeypatch):
    def cancel(*_args):
        raise workflow.launcher.Stopped()
    monkeypatch.setattr(workflow, 'execute', cancel)
    assert rig.worker() == 130
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    assert checkpoint['in_flight'] is True and checkpoint['task_id'] == '001'
    assert TaskBudget(rig.run).read()['completed'] == 0
    assert rig.cleanups == [rig.run]


@pytest.mark.parametrize('consolidated', [False, True])
def test_interrupted_partial_closeout_resumes_without_a_brief(rig, monkeypatch, consolidated):
    previous = rig.root / 'previous'
    previous.mkdir()
    state = state_for(rig.plan, in_flight=True, task_sessions=2)
    if consolidated:
        state['consolidation_obligations'] = {'001': [dict(task_id='original',
            scope='Original history', brief='Retain the complete history.', acceptance='host', targets=[])]}
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    (rig.root / 'docs/001.md').unlink()
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    recovered = workflow.initial_state(rig.plan, rig.spec, rig.root)
    assert recovered['task_id'] == '001' and recovered['session_limit'] == 7
    assert recovered['recovery_run'] == str(previous)
    def restore(root, spec, run, owner):
        (root / 'docs/001.md').write_text('Acceptance: host\n')
        recovered_state = json.loads((run / 'checkpoint.json').read_text())
        complete(rig.plan, '001')
        return response(recovered_state)
    monkeypatch.setattr(workflow, 'execute', restore)
    assert rig.worker(recovered) == 0
    assert TaskBudget(rig.run).read()['completed'] == 1
    assert rig.cleanups == [previous, rig.run, rig.run]


def test_recovery_refuses_unrelated_queue_changes(rig):
    state = state_for(rig.plan, in_flight=True)
    queue = rig.root / rig.plan.queue
    queue.write_text(queue.read_text().replace('| [ ] | 002 |', '| [x] | 002 |'))
    with pytest.raises(ValueError, match='outside its selected task'):
        rig.plan.validate_recovery(state)


def test_public_entry_allows_checkpoint_recovery_before_strict_brief_validation(rig, monkeypatch):
    previous = rig.root / 'previous'
    previous.mkdir()
    workflow.launcher.atomic(previous / 'checkpoint.json', state_for(rig.plan, in_flight=True))
    retained_info = dict(task_id='001', explanation='Checks the child countdown.',
                         last_error='The countdown stopped.', last_error_at=1000.0,
                         status='Root cause identified, fixing')
    workflow.launcher.atomic(previous / 'task-info.json', retained_info)
    (rig.root / 'docs/001.md').unlink()
    monkeypatch.setattr(workflow, '__file__', str(rig.root / 'tools/plan_launcher.py'))
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    monkeypatch.setattr(workflow, 'session_command', lambda *_args: [])
    def select(root, name, command, **options):
        command(rig.run, -1)
        options['on_start'](rig.run)
        return rig.run, True
    monkeypatch.setattr(workflow.launcher, 'select', select)
    monkeypatch.setattr(workflow.launcher, 'follow', lambda *_args, **_kwargs: 0)
    assert workflow.main(rig.spec, []) == 0
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    assert checkpoint['task_id'] == '001' and checkpoint['in_flight'] is True
    assert 'Reconcile interrupted close-out' in checkpoint['handoff']
    assert json.loads((rig.run / 'task-info.json').read_text()) == retained_info
    display = TaskDisplay(Terminal(400, 36), run=rig.run,
                          terminal_size=lambda: os.terminal_size((400, 36)))
    workflow.launcher.atomic(rig.run / 'chat-state.json', {'task_id': '001'})
    display.refresh_chat()
    display.update([dict(key='001', lines=['Task 001: Countdown'])], [])
    assert 'Last Error: The countdown stopped.' in ''.join(row.plain for row in display.previous)


@pytest.mark.parametrize('damage', ['master', 'queue', 'brief'])
def test_public_entry_resumes_rejected_partial_edits_before_strict_metadata_validation(rig, monkeypatch, damage):
    previous = rig.root / 'previous'
    previous.mkdir()
    state = state_for(rig.plan, phase='recover', task_sessions=1,
                      plan_queue=rig.plan.queue,
                      result_recovery={'reason': 'rejected partial close-out',
                                       'response': str(previous / 'rejected-agent-result.json')})
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    path = {'master': rig.plan.path, 'queue': rig.plan.queue, 'brief': 'docs/001.md'}[damage]
    (rig.root / path).write_text('Partial edit requiring correction.\n')
    monkeypatch.setattr(workflow, '__file__', str(rig.root / 'tools/plan_launcher.py'))
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    monkeypatch.setattr(workflow, 'session_command', lambda *_args: [])
    def select(root, name, command, **options):
        command(rig.run, -1)
        options['on_start'](rig.run)
        return rig.run, True
    monkeypatch.setattr(workflow.launcher, 'select', select)
    monkeypatch.setattr(workflow.launcher, 'follow', lambda *_args, **_kwargs: 0)
    assert workflow.main(rig.spec, []) == 0
    restored = json.loads((rig.run / 'checkpoint.json').read_text())
    assert restored['task_id'] == '001' and restored['queue_before'] == state['queue_before']
    assert restored['task']['acceptance'] == 'host' and restored['session_limit'] == 6
    assert restored['result_recovery'] == state['result_recovery']


def test_reattached_observer_counts_legacy_unlimited_run_without_changing_budget(rig, monkeypatch):
    # This owner is already running code from before numeric totals were saved.
    budget = TaskBudget(rig.run)
    budget.initialize(0)
    original = (rig.run / 'limits.json').read_text()
    monkeypatch.setattr(workflow, '__file__', str(rig.root / 'tools/plan_launcher.py'))

    def select(root, name, command, **options):
        options['on_attach'](rig.run)
        return rig.run, False

    def follow(run, **options):
        view = options['view']
        assert view.progress(run, [], [])[0]['lines'] == ['Tasks: 0/2/2']
        assert (run / 'limits.json').read_text() == original
        # Later task completion and explicit limits use current plan data.
        complete(rig.plan, '001')
        budget.complete()
        assert view.progress(run, [], [])[0]['lines'] == ['Tasks: 1/1/2']
        budget.set_limit(3)
        assert view.progress(run, [], [])[0]['lines'] == ['Tasks: 1/2/3']
        return 0

    monkeypatch.setattr(workflow.launcher, 'select', select)
    monkeypatch.setattr(workflow.launcher, 'follow', follow)
    assert workflow.main(rig.spec, []) == 0


def test_e2e_observer_counts_legacy_unlimited_run(tmp_path, monkeypatch):
    import launcher_view
    TaskBudget(tmp_path).initialize(0)
    monkeypatch.setattr(launcher_view, 'e2e_totals', lambda: (17, 9, 26))
    assert view_for('write-e2e').progress(tmp_path, [], [])[0]['lines'] == ['Tasks: 0/9/9']


@pytest.mark.parametrize('action', ['attach', 'limit', 'stop'])
@pytest.mark.parametrize('damage', ['master', 'queue', 'missing-master'])
def test_active_plan_attachment_and_stop_do_not_require_parseable_metadata(rig, monkeypatch, action, damage):
    if damage == 'missing-master':
        (rig.root / rig.plan.path).unlink()
    else:
        (rig.root / (rig.plan.path if damage == 'master' else rig.plan.queue)).write_text('Partial edit\n')
    monkeypatch.setattr(workflow, '__file__', str(rig.root / 'tools/plan_launcher.py'))
    monkeypatch.setattr(workflow.launcher, 'follow', lambda *_args, **_kwargs: 0)
    seen = []
    def select(root, name, command, **options):
        assert root == rig.root and name == 'plans'
        assert options['namespace'] == rig.plan.namespace
        assert options['stop'] == (action == 'stop')
        options['on_attach'](rig.run)
        if options['stop']:
            (rig.run / options['stop_marker']).touch()
        seen.append(rig.run)
        return rig.run, False
    monkeypatch.setattr(workflow.launcher, 'select', select)
    args = ['--stop'] if action == 'stop' else ['--tasks', '3'] if action == 'limit' else []
    assert workflow.main(rig.spec, args) == 0
    assert seen == [rig.run]
    assert (rig.run / 'stop').exists() == (action == 'stop')
    assert TaskBudget(rig.run).read()['tasks'] == (3 if action == 'limit' else 1)
    # Read-only validation still refuses the same damaged plan.
    assert workflow.main(rig.spec, ['--check']) == 2


def test_answered_blocker_survives_restart(rig, monkeypatch):
    previous = rig.root / 'previous'
    previous.mkdir()
    state = state_for(rig.plan, phase='blocked', blocker_id='q')
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    workflow.launcher.atomic(previous / 'question.json',
                             dict(id='q', question='Which scope?', answer='Keep the existing scope.'))
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    recovered = workflow.initial_state(rig.plan, rig.spec, rig.root)
    assert recovered['phase'] == 'recover'
    assert recovered['answer'] == dict(question='Which scope?', answer='Keep the existing scope.')


def test_selected_closeout_link_may_change_but_other_metadata_stays_guarded(tmp_path):
    plan = prepare(tmp_path)
    before, structure = plan.state(), plan.structure(selected='001')
    complete(plan, '001')
    queue = tmp_path / plan.queue
    queue.write_text(queue.read_text().replace('[Task 001](001.md)', '[Accepted evidence](evidence.md)'))
    plan.validate_transition(before, '001', complete=True, structure=structure)
    queue.write_text(queue.read_text().replace('finite scope 001', 'reduced acceptance scope'))
    with pytest.raises(ValueError, match='scope or prerequisites changed'):
        plan.validate_transition(before, '001', complete=True, structure=structure)


def queue_estimates(plan):
    queue = plan.root / plan.queue
    text = queue.read_text().replace('| Scope |', '| Scope | Estimate |')
    for task in plan.tasks():
        text = text.replace(f'finite scope {task.id} |', f'finite scope {task.id} | 15–30 min |')
    queue.write_text(text)
    return queue


@pytest.mark.parametrize('legacy', [False, True])
def test_selected_estimate_closeout_preserves_scope_and_old_checkpoints(tmp_path, legacy):
    plan = prepare(tmp_path)
    queue = queue_estimates(plan)
    state = state_for(plan, in_flight=True)
    if legacy:
        # Old launchers normalized the link, but retained the literal estimate.
        state['queue_structure'][0][6] = '15–30 min'
    original = json.dumps(state, sort_keys=True)
    complete(plan, '001')
    queue.write_text(queue.read_text().replace('finite scope 001 | 15–30 min',
                                               'finite scope 001 | Scoped checks passed; cleanup complete'))
    plan.validate_transition(state['queue_before'], '001', complete=True,
                             structure=state['queue_structure'])
    assert plan.validate_recovery(state)['001'] is True
    assert json.dumps(state, sort_keys=True) == original


@pytest.mark.parametrize('identity, field, replacement', [
    ('001', 4, 'changed prerequisite'), ('001', 5, 'reduced scope'),
    ('002', 3, '[Different task](002.md)'), ('002', 5, 'changed other scope'),
    ('002', 6, 'unrelated estimate edit'),
])
def test_estimate_normalization_keeps_other_queue_fields_guarded(tmp_path, identity, field, replacement):
    plan = prepare(tmp_path)
    queue = queue_estimates(plan)
    state = state_for(plan, in_flight=True)
    complete(plan, '001')
    lines = queue.read_text().splitlines()
    for number, line in enumerate(lines):
        if line.startswith(f'| [x] | {identity} |') or line.startswith(f'| [ ] | {identity} |'):
            fields = line.split('|')
            fields[field] = f' {replacement} '
            lines[number] = '|'.join(fields)
    queue.write_text('\n'.join(lines) + '\n')
    with pytest.raises(ValueError):
        plan.validate_transition(state['queue_before'], '001', complete=True,
                                 structure=state['queue_structure'])
    with pytest.raises(ValueError, match='outside its selected task'):
        plan.validate_recovery(state)


def completed_evidence_plan(root):
    plan = prepare(root, count=3)
    queue = queue_estimates(plan)
    complete(plan, '001')
    evidence = ('15–30 min; 551/551 [checks](../output/test-runs/host/reports/old/report.md), '
                '313/313 [consistency](../output/test-runs/host/reports/older/report.md); cleanup complete')
    queue.write_text(queue.read_text().replace('finite scope 001 | 15–30 min',
                                               f'finite scope 001 | {evidence}'))
    return plan, queue, evidence


@pytest.mark.parametrize('finished', [False, True])
@pytest.mark.parametrize('legacy', [False, True])
def test_completed_evidence_destinations_allow_transition_and_recovery(tmp_path, finished, legacy):
    plan, queue, evidence = completed_evidence_plan(tmp_path)
    state = state_for(plan, in_flight=True)
    if legacy:
        state['queue_structure'] = plan.structure()  # Literal pre-normalization checkpoint.
    checkpoint = json.dumps(state, sort_keys=True)
    replacement = evidence.replace('../output/test-runs/host/reports/old/report.md',
                                   '../output/test-runs/host/plans/plan/run/agent-result.json').replace(
        '../output/test-runs/host/reports/older/report.md',
        '../output/test-runs/host/plans/plan/run/agent-commands.log')
    queue.write_text(queue.read_text().replace(evidence, replacement))
    if finished:
        complete(plan, '002')
    plan.validate_transition(state['queue_before'], '002', complete=finished,
                             structure=state['queue_structure'])
    assert plan.validate_recovery(state)['002'] is finished
    # New snapshots retain the exact evidence URLs, and old state is untouched.
    assert next(row for row in plan.structure() if row[2] == '001')[6] == replacement
    assert json.dumps(state, sort_keys=True) == checkpoint


@pytest.mark.parametrize('defect', [
    'label', 'count', 'prose', 'timing', 'unfinished-estimate', 'scope', 'requires',
    'task-link', 'order', 'completion', 'code', 'image', 'title', 'pipe', 'placeholder',
])
def test_completed_evidence_repair_preserves_every_other_obligation(tmp_path, defect):
    plan, queue, evidence = completed_evidence_plan(tmp_path)
    if defect in ('code', 'image', 'title'):
        extra = {'code': '`[literal](old.md)`', 'image': '![image](old.md)',
                 'title': '[complex](old.md "retained title")'}[defect]
        queue.write_text(queue.read_text().replace(evidence, evidence + '; ' + extra))
    if defect == 'unfinished-estimate':
        queue.write_text(queue.read_text().replace('finite scope 003 | 15–30 min',
                                                   'finite scope 003 | [checks](old.md)'))
    state = state_for(plan, in_flight=True)
    text = queue.read_text()
    if defect == 'label':
        text = text.replace('[checks]', '[different claim]')
    elif defect == 'count':
        text = text.replace(evidence, evidence + '; [extra](new.md)')
    elif defect == 'prose':
        text = text.replace('cleanup complete', 'cleanup unnecessary')
    elif defect == 'timing':
        text = text.replace('15–30 min; 551/551', '1 min; 551/551')
    elif defect == 'unfinished-estimate' or defect in ('code', 'image', 'title'):
        text = text.replace('old.md', 'new.md')
    elif defect in ('scope', 'requires', 'task-link'):
        fields = {'scope': ('finite scope 001', 'reduced scope'),
                  'requires': ('| — | finite scope 001', '| Baseline | finite scope 001'),
                  'task-link': ('[Task 001](001.md)', '[Task 001](different.md)')}
        text = text.replace(*fields[defect])
    elif defect == 'order':
        lines = text.splitlines()
        first = next(i for i, line in enumerate(lines) if line.startswith('| [x] | 001 |'))
        last = next(i for i, line in enumerate(lines) if line.startswith('| [ ] | 003 |'))
        lines[first], lines[last] = lines[last], lines[first]
        text = '\n'.join(lines) + '\n'
    elif defect == 'completion':
        text = text.replace('| [x] | 001 |', '| [ ] | 001 |')
    elif defect == 'pipe':
        text = text.replace('/old/report.md)', '/old/report.md|injected)')
    elif defect == 'placeholder':
        text = text.replace('../output/test-runs/host/reports/old/report.md',
                            '<completed evidence destination>')
    queue.write_text(text)
    with pytest.raises(ValueError):
        plan.validate_transition(state['queue_before'], '002', complete=False,
                                 structure=state['queue_structure'])
    with pytest.raises(ValueError):
        plan.validate_recovery(state)


def test_completed_evidence_repair_survives_retained_restart(rig, monkeypatch):
    # Use the normal restart route with a literal old queue snapshot.
    plan, queue, evidence = completed_evidence_plan(rig.root / 'evidence-plan')
    previous = rig.root / 'previous'
    previous.mkdir()
    state = state_for(plan, in_flight=True, task_sessions=2, total_sessions=4)
    state['queue_structure'] = plan.structure()
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    original = (previous / 'checkpoint.json').read_bytes()
    queue.write_text(queue.read_text().replace(evidence, evidence.replace('/old/', '/retained/')))
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    recovered = workflow.initial_state(plan, rig.spec, rig.root)
    assert recovered['task_id'] == '002' and recovered['task_sessions'] == 2
    assert recovered['total_sessions'] == 4 and recovered.get('pending_completion') is None
    assert (previous / 'checkpoint.json').read_bytes() == original


@pytest.mark.parametrize('rejection', [None, 'retained', 'source'])
def test_retained_completion_recovers_estimate_closeout_without_another_session(rig, monkeypatch, rejection):
    previous = rig.root / 'previous'
    previous.mkdir()
    queue = queue_estimates(rig.plan)
    state = state_for(rig.plan, in_flight=True, task_sessions=2, total_sessions=3)
    # Keep the original literal estimate to exercise existing retained runs.
    state['queue_structure'][0][6] = '15–30 min'
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    result = response(state)
    workflow.launcher.atomic(previous / 'agent-result.json', result)
    complete(rig.plan, '001')
    queue.write_text(queue.read_text().replace('finite scope 001 | 15–30 min',
                                               'finite scope 001 | Acceptance and cleanup passed'))
    (rig.root / 'docs/001.md').unlink()
    if rejection:
        state.update(phase='recover', in_flight=False, task_sessions=5, total_sessions=6,
                     reason='task session limit reached; resume with a fresh run')
        workflow.retain_result_rejection(previous, workflow.SessionResultRejected(
            'task scope or prerequisites changed; retain the queue for review', result),
            label=rig.spec.name, checkpoint=state)
        if rejection == 'source':
            # An interruption while retaining rejection leaves the canonical
            # response as its reference; no older rejected copy may be adopted.
            state['result_recovery']['response'] = str(previous / 'agent-result.json')
            (previous / 'rejected-agent-result.json').write_text('stale rejection')
            workflow.launcher.atomic(previous / 'checkpoint.json', state)
    retained = (previous / 'checkpoint.json').read_bytes()
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    recovered = workflow.initial_state(rig.plan, rig.spec, rig.root)
    assert (previous / 'checkpoint.json').read_bytes() == retained
    assert recovered['pending_completion'] == result and not recovered['in_flight']
    assert recovered['task_sessions'] == (5 if rejection else 2)
    assert recovered['total_sessions'] == (6 if rejection else 3)
    assert 'result_recovery' not in recovered
    assert recovered['handoff'] == result['handoff']
    events = []
    monkeypatch.setattr(workflow.launcher, 'finish_nested', lambda root, run: events.append(('cleanup', run)))
    monkeypatch.setattr(workflow, 'stage_task', lambda root, paths, **kwargs:
                        events.append(('stage', paths)) or paths)
    monkeypatch.setattr(workflow, 'finish_commit', lambda *_args: events.append(('commit', None)))
    monkeypatch.setattr(workflow, 'git_output', lambda root, *args, **kwargs:
                        events.append((args[0], None)) or SimpleNamespace(returncode=0))
    owner = os.open(rig.run / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
    spec = replace(rig.spec, commit_prefix='Fixture', push=True)
    assert workflow.worker(rig.root, rig.run, owner, spec, recovered) == 0
    assert rig.calls == []
    assert [event[0] for event in events] == ['cleanup', 'cleanup', 'stage', 'commit', 'push', 'cleanup']
    assert events[0][1] == previous
    assert TaskBudget(rig.run).read()['completed'] == 1
    final = json.loads((rig.run / 'checkpoint.json').read_text())
    assert final['phase'] == 'complete' and 'pending_completion' not in final
    assert rig.plan.next_task().id == '002'


def test_rejected_completion_recovers_predecessor_evidence_repairs(rig, monkeypatch):
    plan, queue, evidence = completed_evidence_plan(rig.root / 'evidence-plan')
    state = state_for(plan, phase='recover', in_flight=False, task_sessions=5, total_sessions=6)
    state['queue_structure'] = plan.structure()  # Literal older controller snapshot.
    result = response(state)
    workflow.launcher.atomic(rig.run / 'agent-result.json', result)
    workflow.retain_result_rejection(rig.run, workflow.SessionResultRejected(
        'task scope or prerequisites changed; retain the queue for review', result),
        label=rig.spec.name, checkpoint=state)
    original = (rig.run / 'checkpoint.json').read_bytes()
    queue.write_text(queue.read_text().replace(evidence, evidence.replace('/old/', '/retained/')))
    complete(plan, '002')
    (plan.root / 'docs/002.md').unlink()
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    recovered = workflow.initial_state(plan, rig.spec, rig.root)
    assert recovered['pending_completion'] == result and 'result_recovery' not in recovered
    assert recovered['queue_before'] == state['queue_before']
    assert recovered['queue_structure'] == state['queue_structure']
    assert recovered['task_sessions'] == 5 and recovered['total_sessions'] == 6
    assert (rig.run / 'checkpoint.json').read_bytes() == original


@pytest.mark.parametrize('defect', [
    'wrong-task', 'failed-check', 'unfinished-cleanup', 'scope', 'targets', 'agent-error',
    'different-response', 'foreign-reference', 'missing-source', 'missing-retained',
])
def test_rejected_completion_recovery_preserves_response_and_acceptance_guards(rig, monkeypatch, defect):
    state = state_for(rig.plan, phase='recover', in_flight=False, task_sessions=5)
    result = response(state)
    if defect == 'wrong-task':
        result['task_id'] = '002'
    elif defect == 'failed-check':
        result['checks'][0]['result'] = 'failed'
    elif defect == 'unfinished-cleanup':
        result['cleanup_complete'] = False
    workflow.launcher.atomic(rig.run / 'agent-result.json', result)
    workflow.retain_result_rejection(rig.run, workflow.SessionResultRejected('old guard', result),
                                     label=rig.spec.name, checkpoint=state)
    complete(rig.plan, '001')
    if defect == 'scope':
        queue = rig.root / rig.plan.queue
        queue.write_text(queue.read_text().replace('finite scope 001', 'reduced scope'))
    elif defect == 'targets':
        (rig.root / 'docs/001.md').write_text('Acceptance: host\nTargets: other\n')
    elif defect == 'agent-error':
        workflow.launcher.atomic(rig.run / 'agent-error.json', {'message': 'provider refused'})
    elif defect == 'different-response':
        workflow.launcher.atomic(rig.run / 'agent-result.json', dict(result, summary='Different turn'))
    elif defect == 'foreign-reference':
        state['result_recovery']['response'] = str(rig.root / 'foreign/agent-result.json')
    elif defect in ('missing-source', 'missing-retained'):
        (rig.run / ('agent-result.json' if defect == 'missing-source'
                    else 'rejected-agent-result.json')).unlink()
    workflow.launcher.atomic(rig.run / 'checkpoint.json', state)
    original = (rig.run / 'checkpoint.json').read_bytes()
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    recovered = workflow.initial_state(rig.plan, rig.spec, rig.root)
    assert 'pending_completion' not in recovered
    assert recovered['result_recovery'] == state['result_recovery']
    assert recovered['queue_before'] == state['queue_before']
    assert recovered['task_sessions'] == 5
    assert (rig.run / 'checkpoint.json').read_bytes() == original
    assert not rig.calls and TaskBudget(rig.run).read()['completed'] == 0


@pytest.mark.parametrize('defect', ['wrong-task', 'failed-check', 'unfinished-cleanup', 'scope'])
def test_retained_completion_cannot_bypass_acceptance_or_queue_guards(rig, monkeypatch, defect):
    previous = rig.root / 'previous'
    previous.mkdir()
    state = state_for(rig.plan, in_flight=True)
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    result = response(state)
    if defect == 'wrong-task':
        result['task_id'] = '002'
    elif defect == 'failed-check':
        result['checks'][0]['result'] = 'failed'
    elif defect == 'unfinished-cleanup':
        result['cleanup_complete'] = False
    complete(rig.plan, '001')
    if defect == 'scope':
        queue = rig.root / rig.plan.queue
        queue.write_text(queue.read_text().replace('finite scope 001', 'reduced scope'))
    workflow.launcher.atomic(previous / 'agent-result.json', result)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    with pytest.raises(ValueError):
        workflow.initial_state(rig.plan, rig.spec, rig.root)
    assert rig.calls == [] and TaskBudget(rig.run).read()['completed'] == 0
    assert json.loads((previous / 'checkpoint.json').read_text()) == state


def test_new_inflight_checkpoint_cannot_retain_preceding_session_result(rig, monkeypatch):
    workflow.launcher.atomic(rig.run / 'agent-result.json', response(state_for(rig.plan), 'continue'))
    atomic = workflow.launcher.atomic
    checkpoints = []

    def write(path, value):
        if path.name == 'checkpoint.json' and value.get('in_flight') and not checkpoints:
            checkpoints.append(value['task_id'])
            assert not (rig.run / 'agent-result.json').exists()
            raise workflow.launcher.Stopped()
        atomic(path, value)

    monkeypatch.setattr(workflow.launcher, 'atomic', write)
    assert rig.worker() == 130
    assert checkpoints == ['001'] and rig.calls == []
    assert TaskBudget(rig.run).read()['completed'] == 0


def test_accepted_pending_completion_counts_toward_restarted_limit(rig):
    state = state_for(rig.plan)
    state['pending_completion'] = response(state)
    complete(rig.plan, '001')
    assert rig.worker(state) == 0
    assert rig.calls == []
    assert TaskBudget(rig.run).read()['completed'] == 1
    assert rig.plan.next_task().id == '002'


def test_closeout_stages_only_claimed_files(rig, monkeypatch):
    state = state_for(rig.plan)
    state['pending_completion'] = response(state)
    complete(rig.plan, '001')
    (rig.root / 'unrelated.py').write_text('# Concurrent work outside the claimed task.\n')
    staged, committed = [], []
    monkeypatch.setattr(workflow, 'stage_task', lambda root, paths, **kwargs: staged.extend(paths) or paths)
    monkeypatch.setattr(workflow, 'finish_commit', lambda root, run, state, paths, message: committed.extend(paths))
    workflow.closeout(rig.plan, replace(rig.spec, commit_prefix='Fixture'), rig.run, state)
    assert staged == committed == ['docs/plan.md', 'docs/queue.md']
    assert 'unrelated.py' not in staged


@pytest.mark.parametrize('publication_fails', [False, True])
def test_closeout_preserves_proof_after_cleanup_before_git(rig, monkeypatch, publication_fails):
    state = state_for(rig.plan)
    state['pending_completion'] = response(state)
    complete(rig.plan, '001')
    events = []
    monkeypatch.setattr(workflow.launcher, 'finish_nested', lambda *_: events.append('cleanup'))

    def preserve(plan, run, accepted, result):
        events.append('proof')
        assert accepted is state and result is state['pending_completion']
        assert result['cleanup_complete'] is True
        if publication_fails:
            raise ValueError('exact proof unavailable')

    monkeypatch.setattr(workflow.plan_evidence, 'preserve', preserve)
    monkeypatch.setattr(workflow, 'pull_before_commit', lambda *_, **__: events.append('pull'))
    monkeypatch.setattr(workflow, 'stage_task', lambda _, paths, **__: events.append('stage') or paths)
    monkeypatch.setattr(workflow, 'finish_commit', lambda *_: events.append('commit'))
    if publication_fails:
        with pytest.raises(ValueError, match='exact proof unavailable'):
            workflow.closeout(rig.plan, rig.spec, rig.run, state)
        assert events == ['cleanup', 'proof']
        assert state['pending_completion']['status'] == 'task_complete'
    else:
        assert workflow.closeout(rig.plan, rig.spec, rig.run, state)
        assert events == ['cleanup', 'proof', 'pull', 'stage', 'commit']


@pytest.mark.parametrize('exhausted', [False, True])
def test_missing_publication_proof_renews_acceptance_with_original_limits_and_ownership(
        rig, monkeypatch, exhausted):
    state = state_for(rig.plan, task_sessions=1, total_sessions=3,
                      session_limit=1 if exhausted else 5,
                      protected_staged=['unrelated.md'], stage_baseline={'owned.md': 'original'})
    original = response(state)
    state['pending_completion'] = original
    complete(rig.plan, '001')
    (rig.root / 'docs/001.md').unlink()
    attempts, staged = [], []
    source = str(rig.run / 'accepted-source/exact')
    monkeypatch.setattr(workflow.plan_evidence, '_source',
                        lambda plan, run, saved, result: saved.update(evidence_source={'path': source}))

    def preserve(plan, run, saved, result):
        attempts.append(result)
        if len(attempts) == 1:
            raise workflow.plan_evidence.EvidenceUnavailable(['/report.md'])

    def execute(root, spec, run, owner):
        saved = json.loads((run / 'checkpoint.json').read_text())
        assert saved['evidence_renewal']['result'] == original
        assert saved['protected_staged'] == ['unrelated.md']
        assert saved['stage_baseline'] == {'owned.md': 'original'}
        assert saved['queue_before'] == state['queue_before']
        assert 'pending_completion' not in saved and not staged
        assert 'rerun checks whose detailed proof is lost' in (run / 'prompt.txt').read_text()
        (rig.root / 'docs/001.md').write_text('Acceptance: host\n')
        rig.calls.append(saved['task_sessions'])
        return dict(original, summary='Fresh acceptance with available proof')

    monkeypatch.setattr(workflow.plan_evidence, 'preserve', preserve)
    monkeypatch.setattr(workflow, 'execute', execute)
    monkeypatch.setattr(workflow, 'stage_task', lambda _, paths, **__: staged.extend(paths) or paths)
    assert rig.worker(state) == (1 if exhausted else 0)
    saved = json.loads((rig.run / 'checkpoint.json').read_text())
    assert rig.calls == ([] if exhausted else [2])
    assert TaskBudget(rig.run).read()['completed'] == (0 if exhausted else 1)
    if exhausted:
        assert saved['evidence_renewal']['result'] == original and not staged
        monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
        restored = workflow.initial_state(rig.plan, rig.spec, rig.root)
        assert restored['evidence_renewal'] == saved['evidence_renewal']
        assert 'pending_completion' not in restored
        assert restored['queue_before'] == saved['queue_before']
        assert restored['session_limit'] == restored['task_sessions'] + rig.spec.max_sessions
    else:
        assert 'evidence_renewal' not in saved and len(attempts) == 2


@pytest.mark.parametrize('transaction', ['commit_intent', 'pull_intent', 'git_reconciliation'])
def test_unavailable_proof_does_not_renew_across_git_transaction(rig, monkeypatch, transaction):
    state = state_for(rig.plan, **{transaction: {'retained': True}})
    original = response(state)
    state['pending_completion'] = original
    complete(rig.plan, '001')
    def preserve(*_):
        raise workflow.plan_evidence.EvidenceUnavailable(['/expired.md'])
    monkeypatch.setattr(workflow.plan_evidence, 'preserve', preserve)
    with pytest.raises(workflow.plan_evidence.EvidenceUnavailable):
        workflow.closeout(rig.plan, rig.spec, rig.run, state)
    assert state['pending_completion'] == original
    assert 'evidence_renewal' not in state and state[transaction] == {'retained': True}
    assert TaskBudget(rig.run).read()['completed'] == 0


@pytest.mark.parametrize('status', ['continue', 'blocked', 'prerequisite_required'])
def test_unfinished_renewal_survives_valid_handoffs_and_fresh_controller(rig, monkeypatch, status):
    state = state_for(rig.plan, phase='recover', task_sessions=1, total_sessions=3,
                      session_limit=2, plan_queue=rig.plan.queue)
    renewal = dict(reason='Exact proof expired', result=response(state),
                   evidence_source=dict(path=str(rig.run / 'accepted-source/exact')))
    state['evidence_renewal'] = renewal
    def execute(root, spec, run, owner):
        saved = json.loads((run / 'checkpoint.json').read_text())
        if saved['task_id'] == 'pre':
            assert saved['suspended_tasks']['001']['evidence_renewal'] == renewal
            (run / 'stop').touch()
            return response(saved, 'continue')
        assert saved['evidence_renewal'] == renewal
        if status == 'prerequisite_required':
            insert_unlinked_prerequisite(rig.plan, '001')
            queue = root / rig.plan.queue
            queue.write_text(queue.read_text().replace('| — | finite scope 001', '| pre | finite scope 001'))
        result = response(saved, status)
        if status == 'blocked':
            result['blocker'] = dict(explanation='A developer decision is required.',
                question='Which route is authorized?', options=['Preserve the boundary.', 'Authorize the route.'])
        return result
    monkeypatch.setattr(workflow, 'execute', execute)
    monkeypatch.setattr(workflow, 'wait_for_answer', lambda *_, **__: None)
    assert rig.worker(state) == (1 if status == 'continue' else 0)
    saved = json.loads((rig.run / 'checkpoint.json').read_text())
    consumer = saved['suspended_tasks']['001'] if status == 'prerequisite_required' else saved
    assert consumer['evidence_renewal'] == renewal
    assert TaskBudget(rig.run).read()['completed'] == 0
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    restored = workflow.initial_state(rig.plan, rig.spec, rig.root)
    consumer = restored['suspended_tasks']['001'] if status == 'prerequisite_required' else restored
    assert consumer['evidence_renewal'] == renewal
    assert 'pending_completion' not in consumer


@pytest.mark.parametrize('failure', ['pull', 'stage', 'commit', 'push'])
def test_default_git_failure_retains_acceptance_and_retries_before_next_task(rig, monkeypatch, failure):
    events = []
    failing = [True]

    def operation(name):
        events.append(name)
        assert TaskBudget(rig.run).read()['completed'] == 0
        if name == failure and failing[0] and name != 'push':
            raise ValueError(f'completion {name} failed: private failure')

    def stage(root, paths, **kwargs):
        operation('stage')
        assert kwargs['required_paths'] == (rig.plan.path, rig.plan.queue)
        return paths

    def pull(*args, **kwargs):
        operation('pull')

    def commit(root, run, state, paths, message):
        operation('commit')
        assert message == 'TA: Completed task 001'

    def git(root, *args, **kwargs):
        if args == ('push',):
            operation('push')
            if failure == 'push' and failing[0]:
                return SimpleNamespace(stdout='', stderr='private failure', returncode=1)
        return SimpleNamespace(stdout='', stderr='', returncode=0)

    monkeypatch.setattr(workflow, 'stage_task', stage)
    monkeypatch.setattr(workflow, 'finish_commit', commit)
    monkeypatch.setattr(workflow, 'pull_before_commit', pull)
    monkeypatch.setattr(workflow, 'git_output', git)
    TaskBudget(rig.run).initialize(0)
    assert rig.worker() == 1
    saved = json.loads((rig.run / 'checkpoint.json').read_text())
    assert saved['pending_completion']['status'] == 'task_complete'
    assert saved['phase'] != 'complete'
    assert rig.calls == [('001', 1, 'xhigh')]
    assert TaskBudget(rig.run).read()['completed'] == 0
    assert f'completion {failure} failed' in (rig.run / 'handoff.txt').read_text()

    # A fresh run closes the accepted task without another agent session.
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    recovered = workflow.initial_state(rig.plan, rig.spec, rig.run.parent)
    failing[0] = False
    events.clear()
    TaskBudget(rig.run).initialize(1)
    assert rig.worker(recovered) == 0
    assert events == ['pull', 'stage', 'commit', 'push']
    assert rig.calls == [('001', 1, 'xhigh')]
    assert TaskBudget(rig.run).read()['completed'] == 1
    assert rig.plan.next_task().id == '002'


@pytest.mark.parametrize('protected', ['stage_baseline', 'protected_staged'])
def test_closeout_refuses_preexisting_claimed_changes(rig, monkeypatch, protected):
    state = state_for(rig.plan)
    state[protected] = {'docs/plan.md': 'original'} if protected == 'stage_baseline' else ['docs/plan.md']
    state['pending_completion'] = response(state)
    complete(rig.plan, '001')
    monkeypatch.setattr(launcher_git, 'committed_fingerprint', lambda *_: 'different committed content')
    monkeypatch.setattr(workflow, 'stage_task', lambda *_args, **_kwargs: pytest.fail('must not stage protected work'))
    monkeypatch.setattr(workflow, 'pull_before_commit', lambda *_args, **_kwargs: pytest.fail('must not pull over protected work'))
    with pytest.raises(ValueError, match='overlaps pre-existing work'):
        workflow.closeout(rig.plan, replace(rig.spec, commit_prefix='Fixture'), rig.run, state)


@pytest.fixture
def git_plan(tmp_path):
    root = tmp_path / 'checkout'
    plan = prepare(root)

    def git(*args, cwd=root, check=True):
        return subprocess.run(['git', *args], cwd=cwd, check=check, capture_output=True,
                              text=True, timeout=10, env=dict(os.environ, LC_ALL='C'))

    git('init', '-q')
    git('config', 'user.name', 'Launcher test')
    git('config', 'user.email', 'launcher@example.invalid')
    (root / '.git/info/exclude').write_text('run/\n')
    (root / 'task.py').write_text('initial task\n')
    (root / 'shared.py').write_text('initial shared\n')
    (root / 'unrelated.py').write_text('initial unrelated\n')
    git('add', '--', 'docs', 'task.py', 'shared.py', 'unrelated.py')
    git('commit', '-qm', 'Private baseline')
    remote = tmp_path / 'remote.git'
    git('init', '--bare', '-q', str(remote))
    git('remote', 'add', 'origin', str(remote))
    git('push', '-qu', 'origin', 'HEAD')
    peer = tmp_path / 'peer'
    git('clone', '-q', str(remote), str(peer))
    git('config', 'user.name', 'Peer test', cwd=peer)
    git('config', 'user.email', 'peer@example.invalid', cwd=peer)
    run = root / 'run'
    run.mkdir()
    return SimpleNamespace(root=root, plan=plan, remote=remote, peer=peer, run=run, git=git)


@pytest.mark.parametrize('kind', ['file', 'binary', 'link', 'deleted', 'executable-on', 'executable-off'])
@pytest.mark.parametrize('committed', ['no', 'exact', 'different'])
def test_closeout_baseline_requires_exact_committed_contents(git_plan, kind, committed):
    f = git_plan
    path = f.root / 'task.py'
    if kind == 'file':
        path.write_text('pre-existing work\n')
    elif kind == 'binary':
        path.write_bytes(b'\xff\x00pre-existing binary\n')
    elif kind == 'link':
        path.unlink()
        path.symlink_to('shared.py')
    elif kind == 'executable-on':
        path.chmod(0o755)
    elif kind == 'executable-off':
        path.chmod(0o755)
        f.git('add', '--', 'task.py')
        f.git('commit', '-qm', 'Executable baseline')
        path.chmod(0o644)
    else:
        path.unlink()
    baseline = workflow.worktree_snapshot(f.root)
    if committed != 'no':
        if committed == 'different':
            path.unlink(missing_ok=True)
            path.write_text('a different committed change\n')
        f.git('add', '--', 'task.py')
        f.git('commit', '-qm', 'Reviewed change')
    path.unlink(missing_ok=True)
    path.write_text('new task work\n')
    if kind == 'executable-on':
        path.chmod(0o755)
    state = dict(stage_baseline=baseline, protected_staged=[])
    if committed == 'exact':
        # Staged ownership is independent and must never be inferred from HEAD.
        state['protected_staged'] = ['task.py']
        with pytest.raises(ValueError, match='overlaps pre-existing work: task.py'):
            launcher_git.validate_closeout_ownership(f.root, ['task.py'], state)
        state['protected_staged'] = []
        launcher_git.validate_closeout_ownership(f.root, ['task.py'], state)
        assert state['stage_baseline'] == {}
    else:
        with pytest.raises(ValueError, match='overlaps pre-existing work: task.py'):
            launcher_git.validate_closeout_ownership(f.root, ['task.py'], state)
        assert state['stage_baseline'] == baseline


@pytest.mark.parametrize('change', ['chmod', 'delete', 'link'])
def test_legacy_file_baseline_refuses_ambiguous_mode_or_type(git_plan, change):
    f = git_plan
    path = f.root / 'task.py'
    path.write_text('pre-existing content\n')
    baseline = workflow.worktree_snapshot(f.root)
    f.git('add', '--', 'task.py')
    f.git('commit', '-qm', 'Reviewed pre-existing content')
    if change == 'chmod':
        path.chmod(0o755)
    else:
        path.unlink()
        if change == 'link':
            path.symlink_to('shared.py')
    state = dict(stage_baseline=baseline, protected_staged=[])
    with pytest.raises(ValueError, match='overlaps pre-existing work: task.py'):
        launcher_git.validate_closeout_ownership(f.root, ['task.py'], state)
    assert state['stage_baseline'] == baseline


@pytest.mark.parametrize('pending', ['none', 'staged', 'unstaged', 'assume-unchanged', 'chmod'])
def test_closeout_releases_clean_committed_file_without_baseline_version_lock(git_plan, pending):
    f = git_plan
    path = f.root / 'task.py'
    path.write_text('captured earlier work\n')
    baseline = workflow.worktree_snapshot(f.root)
    # Another workflow has already committed the task, including a newer report.
    path.write_text('reviewed current contents\n')
    f.git('add', '--', 'task.py')
    f.git('commit', '-qm', 'Reviewed completed work')
    if pending in ('staged', 'unstaged', 'assume-unchanged'):
        path.write_text('pending work\n')
        if pending == 'staged':
            f.git('add', '--', 'task.py')
            path.write_text('reviewed current contents\n')
        elif pending == 'assume-unchanged':
            f.git('update-index', '--assume-unchanged', '--', 'task.py')
    elif pending == 'chmod':
        f.git('config', 'core.filemode', 'false')
        path.chmod(0o755)
    state = dict(stage_baseline=baseline.copy(), replan_baseline=baseline.copy(),
                 protected_staged=[], suspended_tasks={'002': dict(stage_baseline=baseline.copy())})
    if pending == 'none':
        state['protected_staged'] = ['task.py']
        with pytest.raises(ValueError, match='overlaps pre-existing work: task.py'):
            launcher_git.validate_closeout_ownership(f.root, ['task.py'], state)
        state['protected_staged'] = []
        launcher_git.validate_closeout_ownership(f.root, ['task.py'], state)
        assert state['stage_baseline'] == state['replan_baseline'] == {}
        assert state['suspended_tasks']['002']['stage_baseline'] == {}
    else:
        with pytest.raises(ValueError, match='overlaps pre-existing work: task.py'):
            launcher_git.validate_closeout_ownership(f.root, ['task.py'], state)
        assert state['stage_baseline'] == baseline


@pytest.mark.parametrize('pending', [False, True], ids=['inherited-baseline', 'accepted-restart'])
def test_committed_baseline_closes_and_pushes_before_unlimited_advance(git_plan, monkeypatch, pending):
    f = git_plan
    (f.root / 'task.py').write_text('pre-existing work\n')
    (f.root / 'report.md').write_text('earlier generated report\n')
    baseline = workflow.worktree_snapshot(f.root)
    f.git('add', '--', 'task.py')
    f.git('commit', '-qm', 'Reviewed pre-existing work')
    (f.root / 'report.md').write_text('current generated report\n')
    f.git('add', '--', 'report.md')
    f.git('commit', '-qm', 'Reviewed refreshed report')
    # Like a reconciled plan, retain a baseline captured before another workflow
    # committed it. The task must not adopt unrelated dirty or staged changes.
    (f.root / 'unrelated.py').write_text('unrelated unstaged work\n')
    (f.root / 'shared.py').write_text('unrelated staged work\n')
    f.git('add', '--', 'shared.py')
    calls = []

    def accepted(state):
        (f.root / 'task.py').write_text('completed task ' + state['task_id'] + '\n')
        complete(f.plan, state['task_id'])
        result = response(state)
        result['stage_paths'].append('task.py')
        if state['task_id'] == '002':
            # Task 001 must release other clean paths before this consumer edits
            # them; the retained report version must not block the next task.
            assert 'report.md' not in state['stage_baseline']
            (f.root / 'report.md').write_text('next task report\n')
            result['stage_paths'].append('report.md')
        return result

    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        if state['task_id'] == '002':
            assert f.git('log', '-1', '--format=%s').stdout.strip() == 'TA: Completed task 001'
            assert f.git('rev-parse', 'HEAD').stdout == f.git('rev-parse', 'HEAD', cwd=f.remote).stdout
        calls.append(state['task_id'])
        return accepted(state)

    monkeypatch.setattr(workflow, 'execute', execute)
    monkeypatch.setattr(workflow.launcher, 'finish_nested', lambda *_: None)
    monkeypatch.setattr(workflow.signal, 'signal', lambda *_: None)
    spec = workflow.PlanWorkflow('fixture-plan', f.plan.path)
    record = workflow.task_record(f.plan.tasks()[1])
    consumer = dict(state_for(f.plan), **record, task=record, stage_baseline=baseline,
                    protected_staged=['shared.py'])
    if pending:
        state = state_for(f.plan, stage_baseline=baseline, protected_staged=['shared.py'],
                          replan_baseline=baseline, suspended_tasks={'002': consumer})
        state['pending_completion'] = accepted(state)
        # Accepted task edits can already be committed outside this controller.
        # Restart must retire the stale baseline and close out without a session.
        f.git('add', '--', 'task.py', 'docs/plan.md', 'docs/queue.md')
        f.git('commit', '--only', '-qm', 'Reviewed completed task', '--',
              'task.py', 'docs/plan.md', 'docs/queue.md')
        workflow.launcher.atomic(f.run / 'checkpoint.json', state)
        monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: f.run)
        state = workflow.initial_state(f.plan, spec, f.run.parent)
    else:
        state = dict(phase='complete', task_sessions=0, total_sessions=0,
                     replan_baseline=baseline, protected_staged=['shared.py'],
                     suspended_tasks={'002': consumer})
    TaskBudget(f.run).initialize(0)
    owner = os.open(f.run / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
    assert workflow.worker(f.root, f.run, owner, spec, state) == 0
    assert calls == (['002'] if pending else ['001', '002'])
    assert json.loads((f.run / 'result.json').read_text()) == dict(status=0, tasks=2)
    assert f.plan.next_task() is None
    assert f.git('log', '-2', '--format=%s').stdout.splitlines() == [
        'TA: Completed task 002', 'TA: Completed task 001']
    assert f.git('rev-parse', 'HEAD').stdout == f.git('rev-parse', 'HEAD', cwd=f.remote).stdout
    assert f.git('diff', '--cached', '--name-only').stdout.splitlines() == ['shared.py']
    assert (f.root / 'unrelated.py').read_text() == 'unrelated unstaged work\n'
    assert f.git('show', 'HEAD:unrelated.py').stdout == 'initial unrelated\n'


@pytest.fixture
def replan(git_plan):
    from test_storage import directory

    scene = git_plan
    state = state_for(scene.plan, task_sessions=2, total_sessions=7)
    state['pending_completion'] = response(state)
    complete(scene.plan, '001')
    state['suspended_tasks'] = {'002': state_for(scene.plan, task_sessions=3,
        total_sessions=6, in_flight=True, handoff='Unresolved consumer work remains.')}
    queue = scene.root / scene.plan.queue
    queue.write_text(queue.read_text().replace('| [ ] | 002 |',
        '| [ ] | pre | [Preparation](pre.md) | 001 | new prerequisite |\n| [ ] | 002 |'))
    (scene.root / 'docs/pre.md').write_text('Acceptance: host\n')
    (scene.root / scene.plan.path).write_text('Task queue: [Queue](queue.md).\nNext task: **pre — Preparation**.\n')
    scene.git('add', '--', 'docs')
    scene.git('commit', '-qm', 'Reviewed accepted work and replan')
    namespace = workflow.launcher.private_directory(directory('plans', root=scene.root) / scene.plan.namespace)
    scene.run = workflow.launcher.private_directory(namespace / ('a' * 32))
    workflow.launcher.atomic(namespace / 'current.json', dict(run=scene.run.name))
    workflow.launcher.atomic(scene.run / 'checkpoint.json', state)
    workflow.launcher.atomic(scene.run / 'agent-result.json', state['pending_completion'])
    workflow.launcher.atomic(scene.run / 'result.json', dict(status=1, tasks=0))
    (scene.root / 'shared.py').write_text('unrelated staged work\n')
    scene.git('add', '--', 'shared.py')
    (scene.root / 'unrelated.py').write_text('unrelated unstaged work\n')
    scene.spec = workflow.PlanWorkflow('fixture-plan', scene.plan.path, vm=True)
    return scene


def test_explicit_replan_preserves_evidence_unfinished_work_and_git_state(replan, monkeypatch):
    scene = replan
    raw = (scene.run / 'checkpoint.json').read_bytes()
    head = scene.git('rev-parse', 'HEAD').stdout
    index = scene.git('diff', '--cached').stdout
    worktree = scene.git('diff').stdout
    def unexpected(*_args, **_kwargs):
        pytest.fail('reconciliation attempted task execution, Git mutation or VM selection')
    monkeypatch.setattr(workflow, 'session_command', lambda *_: ['unused-model-command'])
    monkeypatch.setattr(workflow, 'stage_task', unexpected)
    monkeypatch.setattr(workflow, 'finish_commit', unexpected)
    monkeypatch.setattr(workflow, 'execute', unexpected)
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name, check=True) == dict(
        run=scene.run.name, next_task='pre', reconciled=False, checked=True)
    assert (scene.run / 'checkpoint.json').read_bytes() == raw
    assert not list(scene.run.glob('checkpoint-before-reconcile-*'))
    result = workflow.reconcile_plan(scene.root, scene.spec, scene.run.name)
    assert result['reconciled'] and result['next_task'] == 'pre'
    backup, = scene.run.glob('checkpoint-before-reconcile-*')
    assert json.loads(backup.read_text())['checkpoint_utf8'].encode() == raw
    updated = json.loads((scene.run / 'checkpoint.json').read_text())
    assert updated['total_sessions'] == 7 and updated['task_id'] is None
    assert updated['suspended_tasks']['002']['task_sessions'] == 3
    assert updated['suspended_tasks']['002']['handoff'] == 'Unresolved consumer work remains.'
    assert updated['queue_before'] == {'001': True, 'pre': False, '002': False}
    assert 'pending_completion' not in updated
    assert 'shared.py' in updated['protected_staged']
    assert 'unrelated.py' in updated['replan_baseline']
    assert scene.git('rev-parse', 'HEAD').stdout == head
    assert scene.git('diff', '--cached').stdout == index
    assert scene.git('diff').stdout == worktree
    # The actual resume entry validates the reconciled state without a session.
    resumed = workflow.initial_state(scene.plan, scene.spec, scene.run.parent)
    assert resumed['queue_before'] == updated['queue_before']
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name, check=True)['reconciled']
    assert len(list(scene.run.glob('checkpoint-before-reconcile-*'))) == 1


@pytest.mark.parametrize('defect', [
    'wrong-run', 'active', 'in-flight', 'commit-intent', 'pending-pull',
    'cleanup', 'failed-check', 'missing-target', 'completed-consumer',
    'new-completion', 'changed-scope', 'dropped-dependency', 'dirty-plan',
    'blank-evidence', 'malformed-check', 'wrong-consumer-id', 'consumer-counter',
    'consumer-transaction', 'stale-consumer-brief', 'backup-link',
])
def test_explicit_replan_refuses_unaccepted_or_unowned_changes(replan, defect):
    scene = replan
    checkpoint = scene.run / 'checkpoint.json'
    state = json.loads(checkpoint.read_text())
    identity = scene.run.name
    queue = scene.root / scene.plan.queue
    if defect == 'wrong-run': identity = 'b' * 32
    if defect == 'in-flight': state['in_flight'] = True
    if defect == 'commit-intent': state['commit_intent'] = {'parent': 'private-head'}
    if defect == 'pending-pull': state['pull_intent'] = {'head': 'private-head'}
    if defect == 'cleanup': state['pending_completion']['cleanup_complete'] = False
    if defect == 'failed-check': state['pending_completion']['checks'][0]['result'] = 'failed'
    if defect == 'missing-target': state['pending_completion']['checks'][0]['target'] = 'other'
    if defect == 'blank-evidence': state['pending_completion']['checks'][0]['evidence'] = '   '
    if defect == 'malformed-check': state['pending_completion']['checks'][0]['extra'] = True
    if defect == 'wrong-consumer-id': state['suspended_tasks']['002']['task_id'] = '001'
    if defect == 'consumer-counter': state['suspended_tasks']['002']['task_sessions'] = True
    if defect == 'consumer-transaction': state['suspended_tasks']['002']['commit_intent'] = {'parent': 'head'}
    if defect == 'stale-consumer-brief':
        (scene.root / 'docs/002.md').rename(scene.root / 'docs/replacement.md')
        queue.write_text(queue.read_text().replace('(002.md)', '(replacement.md)'))
    if defect == 'completed-consumer': complete(scene.plan, '002')
    if defect == 'new-completion': complete(scene.plan, 'pre')
    if defect == 'changed-scope': queue.write_text(queue.read_text().replace('finite scope 002', 'weaker scope'))
    if defect == 'dropped-dependency': state['queue_structure'][1][4] = '001'
    if defect == 'dirty-plan': queue.write_text(queue.read_text() + '\nUncommitted planning edit\n')
    if defect not in ('dirty-plan',):
        scene.git('add', '--', 'docs')
        scene.git('commit', '--allow-empty', '-qm', 'Private changed plan')
    workflow.launcher.atomic(checkpoint, state)
    workflow.launcher.atomic(scene.run / 'agent-result.json', state['pending_completion'])
    raw = checkpoint.read_bytes()
    if defect == 'backup-link':
        digest = workflow.hashlib.sha256(raw).hexdigest()
        (scene.run / ('checkpoint-before-reconcile-' + digest + '.json')).symlink_to(checkpoint)
    with workflow.launcher.lock(scene.run.parent / 'owner') as owner:
        if defect == 'active':
            workflow.fcntl.flock(owner, workflow.fcntl.LOCK_EX | workflow.fcntl.LOCK_NB)
        with pytest.raises(ValueError):
            workflow.reconcile_plan(scene.root, scene.spec, identity)
    assert checkpoint.read_bytes() == raw
    assert len(list(scene.run.glob('checkpoint-before-reconcile-*'))) == (1 if defect == 'backup-link' else 0)


def test_explicit_replan_retries_interrupted_checkpoint_publication(replan, monkeypatch):
    scene = replan
    checkpoint = scene.run / 'checkpoint.json'
    raw = checkpoint.read_bytes()
    atomic = workflow.launcher.atomic
    def interrupted(path, value):
        if path == checkpoint:
            raise OSError('private interrupted publication')
        atomic(path, value)
    monkeypatch.setattr(workflow.launcher, 'atomic', interrupted)
    with pytest.raises(OSError, match='interrupted publication'):
        workflow.reconcile_plan(scene.root, scene.spec, scene.run.name)
    assert checkpoint.read_bytes() == raw
    backup, = scene.run.glob('checkpoint-before-reconcile-*')
    assert json.loads(backup.read_text())['checkpoint_utf8'].encode() == raw
    monkeypatch.setattr(workflow.launcher, 'atomic', atomic)
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name)['reconciled']
    assert len(list(scene.run.glob('checkpoint-before-reconcile-*'))) == 1


def test_explicit_replan_retries_interrupted_backup_publication(replan, monkeypatch):
    scene = replan
    checkpoint = scene.run / 'checkpoint.json'
    raw = checkpoint.read_bytes()
    atomic = workflow.launcher.atomic
    def interrupted(path, value):
        if path.name.startswith('checkpoint-before-reconcile-'):
            path.with_suffix('.tmp').write_bytes(b'partial backup')
            raise OSError('private interrupted backup')
        atomic(path, value)
    monkeypatch.setattr(workflow.launcher, 'atomic', interrupted)
    with pytest.raises(OSError, match='interrupted backup'):
        workflow.reconcile_plan(scene.root, scene.spec, scene.run.name)
    assert checkpoint.read_bytes() == raw
    monkeypatch.setattr(workflow.launcher, 'atomic', atomic)
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name)['reconciled']
    archive, = scene.run.glob('checkpoint-before-reconcile-*.json')
    assert json.loads(archive.read_text())['checkpoint_utf8'].encode() == raw


def test_reconciled_launcher_executes_first_prerequisite_then_resumes_consumer(replan, monkeypatch):
    scene = replan
    workflow.reconcile_plan(scene.root, scene.spec, scene.run.name)
    calls = []
    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        calls.append((state['task_id'], state['task_sessions']))
        assert state['phase'] == 'implement' if state['task_id'] == 'pre' else state['phase'] == 'recover'
        assert 'shared.py' in state['protected_staged']
        complete(scene.plan, state['task_id'])
        return response(state)
    monkeypatch.setattr(workflow, 'execute', execute)
    original_index = scene.git('diff', '--cached').stdout
    for identity in ('b' * 32, 'c' * 32):
        state = workflow.initial_state(scene.plan, scene.spec, scene.run.parent)
        run = workflow.launcher.private_directory(scene.run.parent / identity)
        TaskBudget(run).initialize(1)
        workflow.launcher.atomic(run.parent / 'current.json', dict(run=identity))
        owner = os.open(run.parent / 'owner', os.O_RDWR)
        assert workflow.worker(scene.root, run, owner, scene.spec, state) == 0
        assert TaskBudget(run).read()['completed'] == 1
        assert scene.git('diff', '--cached').stdout == original_index
    assert calls == [('pre', 1), ('002', 4)]
    assert scene.plan.next_task() is None


def test_public_replan_check_does_not_select_vms_or_start_tasks(replan, monkeypatch, capsys):
    import vm_selection
    scene = replan
    monkeypatch.setattr(workflow, '__file__', str(scene.root / 'tools/plan_launcher.py'))
    def unexpected(*_args, **_kwargs):
        pytest.fail('administrative replan attempted execution')
    monkeypatch.setattr(vm_selection, 'execution_selection', unexpected)
    monkeypatch.setattr(workflow.launcher, 'select', unexpected)
    assert workflow.main(scene.spec, ['--reconcile', scene.run.name, '--check']) == 0
    assert json.loads(capsys.readouterr().out)['next_task'] == 'pre'


@pytest.fixture
def consolidated_plan(git_plan):
    from test_storage import directory

    scene = git_plan
    queue = scene.root / scene.plan.queue
    queue.write_text(queue.read_text().replace('| [ ] | 001 |',
        '| [x] | 000 | Baseline | Baseline | accepted baseline |\n| [ ] | 001 |').replace(
        '| [ ] | 002 | [Task 002](002.md) | — |',
        '| [ ] | 002 | [Task 002](002.md) | 001 |').replace('## Deferred future work',
        '| [ ] | 003 | [Final gate](003.md) | 001, 002 | final gate |\n## Deferred future work'))
    for identity, targets in [('001', 'Ubuntu'), ('002', 'Fedora'), ('003', 'Ubuntu, Fedora')]:
        (scene.root / f'docs/{identity}.md').write_text(f'Acceptance: installed\nTargets: {targets}\n')
    scene.git('add', '--', 'docs')
    scene.git('commit', '-qm', 'Private separate qualification tasks')
    scene.base = scene.git('rev-parse', 'HEAD').stdout.strip()
    state = state_for(scene.plan, task_sessions=1, total_sessions=8,
                      in_flight=True, reason='cancelled after owned cleanup')
    consumer = workflow.task_record(scene.plan.tasks()[3])
    state['suspended_tasks'] = {'003': dict(state_for(scene.plan), **consumer, task=consumer,
        task_sessions=2, total_sessions=5, handoff='Retain both complete histories and their exact inputs.')}
    queue.write_text('\n'.join(line for line in queue.read_text().splitlines()
                                if not line.startswith('| [ ] | 002 |')).replace(
        '[Task 001](001.md)', '[Both targets](combined.md)').replace(
        'finite scope 001', 'both complete histories').replace('001, 002 | final gate', '001 | final gate') + '\n')
    (scene.root / 'docs/combined.md').write_text('Acceptance: installed\nTargets: Ubuntu, Fedora\n'
                                              'finite scope 001\nfinite scope 002\n')
    (scene.root / 'docs/001.md').unlink()
    (scene.root / 'docs/002.md').unlink()
    scene.git('add', '--', 'docs')
    scene.git('commit', '-qm', 'Reviewed combined qualification task')
    namespace = workflow.launcher.private_directory(directory('plans', root=scene.root) / scene.plan.namespace)
    scene.run = workflow.launcher.private_directory(namespace / ('a' * 32))
    workflow.launcher.atomic(namespace / 'current.json', dict(run=scene.run.name))
    workflow.launcher.atomic(scene.run / 'checkpoint.json', state)
    workflow.launcher.atomic(scene.run / 'result.json', dict(status=130, tasks=0))
    workflow.launcher.atomic(scene.run / 'nested.json', [])
    (scene.run / 'cancel').touch()
    (scene.run / 'nested-closed').touch()
    (scene.root / 'shared.py').write_text('unrelated staged work\n')
    scene.git('add', '--', 'shared.py')
    (scene.root / 'unrelated.py').write_text('unrelated unstaged work\n')
    scene.spec = workflow.PlanWorkflow('fixture-plan', scene.plan.path, vm=True)
    return scene


def test_consolidation_recovers_cancelled_owner_preserving_both_targets_and_handoffs(
        consolidated_plan, monkeypatch):
    scene = consolidated_plan
    checkpoint = scene.run / 'checkpoint.json'
    raw = checkpoint.read_bytes()
    head = scene.git('rev-parse', 'HEAD').stdout
    index, worktree = scene.git('diff', '--cached').stdout, scene.git('diff').stdout
    def unexpected(*_args, **_kwargs):
        pytest.fail('administrative reconciliation attempted task execution')
    monkeypatch.setattr(workflow, 'execute', unexpected)
    monkeypatch.setattr(workflow, 'session_command', lambda *_: ['unused-model-command'])
    options = dict(merge_tasks=['002=001'], base=scene.base)
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name, check=True, **options)['checked']
    assert checkpoint.read_bytes() == raw
    assert not list(scene.run.glob('checkpoint-before-reconcile-*'))
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name, **options)['reconciled']
    backup, = scene.run.glob('checkpoint-before-reconcile-*')
    assert json.loads(backup.read_text())['checkpoint_utf8'].encode() == raw
    updated = json.loads(checkpoint.read_text())
    assert updated['queue_before'] == {'000': True, '001': False, '003': False}
    assert updated['total_sessions'] == 8 and updated['task_id'] is None
    active, consumer = (updated['suspended_tasks'][key] for key in ('001', '003'))
    assert active['task_sessions'] == 1 and consumer['task_sessions'] == 2
    assert active['task']['targets'] == ['Ubuntu', 'Fedora']
    assert active['task']['brief'] == str(scene.root / 'docs/combined.md')
    assert consumer['handoff'] == 'Retain both complete histories and their exact inputs.'
    originals = updated['consolidation_obligations']['001']
    assert [item['task_id'] for item in originals] == ['001', '002']
    assert originals[1]['brief'] == 'Acceptance: installed\nTargets: Fedora\n'
    active['consolidation_obligations'] = updated['consolidation_obligations']
    assert 'finite scope 002' in workflow.session_prompt(scene.plan, scene.spec, active)
    assert 'shared.py' in updated['protected_staged'] and 'unrelated.py' in updated['replan_baseline']
    result = response(active)
    result['checks'] = [dict(kind='installed', target='Ubuntu', result='passed', evidence='one history')]
    with pytest.raises(ValueError, match='passing scoped acceptance'):
        workflow.validate_result_payload(active, result)
    assert workflow.initial_state(scene.plan, scene.spec, scene.run.parent)['phase'] == 'complete'
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name, check=True, **options)['resume_ready']
    assert scene.git('rev-parse', 'HEAD').stdout == head
    assert scene.git('diff', '--cached').stdout == index and scene.git('diff').stdout == worktree


@pytest.mark.parametrize('defect', [
    'implicit', 'missing-base', 'wrong-base', 'wrong-map', 'chain', 'completed-source',
    'target-loss', 'kind-change', 'unrelated-scope', 'dropped-dependency', 'saved-source',
    'saved-metadata', 'lost-scope', 'uncancelled', 'unclosed', 'result-mismatch', 'response-present',
    'agent-error', 'nested-owner', 'cancel-symlink', 'cancel-hardlink', 'pending-git',
])
def test_consolidation_refuses_lost_obligations_and_unfinished_owners(consolidated_plan, defect):
    scene = consolidated_plan
    checkpoint = scene.run / 'checkpoint.json'
    state = json.loads(checkpoint.read_text())
    queue = scene.root / scene.plan.queue
    options = dict(merge_tasks=['002=001'], base=scene.base)
    if defect == 'implicit': options = {}
    if defect == 'missing-base': options['base'] = None
    if defect == 'wrong-base': options['base'] = scene.git('rev-parse', scene.base + '^').stdout.strip()
    if defect == 'wrong-map': options['merge_tasks'] = ['missing=001']
    if defect == 'chain': options['merge_tasks'] = ['002=001', '001=003']
    if defect == 'completed-source': state['queue_before']['002'] = True
    if defect == 'target-loss':
        path = scene.root / 'docs/combined.md'
        path.write_text(path.read_text().replace('Ubuntu, Fedora', 'Ubuntu'))
    if defect == 'kind-change':
        (scene.root / 'docs/combined.md').write_text('Acceptance: review\nTargets: Ubuntu, Fedora\n')
    if defect == 'unrelated-scope': queue.write_text(queue.read_text().replace('final gate |', 'weaker gate |'))
    if defect == 'dropped-dependency': queue.write_text(queue.read_text().replace('001 | final gate', '— | final gate'))
    if defect == 'saved-source':
        state['suspended_tasks']['002'] = dict(state, task_id='002', suspended_tasks={})
    if defect == 'saved-metadata': state['task']['targets'] = ['unrelated-target']
    if defect == 'lost-scope':
        path = scene.root / 'docs/combined.md'
        path.write_text(path.read_text().replace('finite scope 002', 'weaker scope'))
    if defect == 'uncancelled': (scene.run / 'cancel').unlink()
    if defect == 'unclosed': (scene.run / 'nested-closed').unlink()
    if defect == 'result-mismatch': workflow.launcher.atomic(scene.run / 'result.json', dict(status=1, tasks=0))
    if defect == 'response-present': workflow.launcher.atomic(scene.run / 'agent-result.json', response(state))
    if defect == 'agent-error': workflow.launcher.atomic(scene.run / 'agent-error.json', {'message': 'failed'})
    if defect == 'nested-owner': workflow.launcher.atomic(scene.run / 'nested.json', [{'path': 'unfinished'}])
    if defect == 'cancel-symlink':
        (scene.run / 'cancel').unlink()
        (scene.run / 'cancel').symlink_to(scene.run / 'nested-closed')
    if defect == 'cancel-hardlink': os.link(scene.run / 'cancel', scene.run / 'other-cancel')
    if defect == 'pending-git': state['commit_intent'] = {'parent': 'private-head'}
    scene.git('add', '--', 'docs')
    scene.git('commit', '--allow-empty', '-qm', 'Private changed replan')
    workflow.launcher.atomic(checkpoint, state)
    raw = checkpoint.read_bytes()
    with pytest.raises(ValueError):
        workflow.reconcile_plan(scene.root, scene.spec, scene.run.name, **options)
    assert checkpoint.read_bytes() == raw
    assert not list(scene.run.glob('checkpoint-before-reconcile-*'))


def test_consolidation_after_completed_task_boundary_keeps_future_obligations(consolidated_plan):
    scene = consolidated_plan
    checkpoint = scene.run / 'checkpoint.json'
    state = json.loads(checkpoint.read_text())
    historical = dict(task_id='000', title='Baseline', brief=str(scene.root / 'docs/retired.md'),
                      acceptance='host', targets=[])
    state.update(historical, task=historical, phase='complete', in_flight=False)
    workflow.launcher.atomic(checkpoint, state)
    workflow.launcher.atomic(scene.run / 'result.json', dict(status=0, tasks=1))
    assert workflow.reconcile_plan(scene.root, scene.spec, scene.run.name,
                                   merge_tasks=['002=001'], base=scene.base)['reconciled']
    updated = workflow.initial_state(scene.plan, scene.spec, scene.run.parent)
    assert set(updated['suspended_tasks']) == {'003'}
    assert updated['consolidation_obligations']['001'][1]['targets'] == ['Fedora']


def test_future_consolidated_obligations_survive_intervening_task_closeout(rig, monkeypatch):
    original = dict(task_id='retired-source', scope='Required future retained-history witness',
                    brief='Preserve native denial and unrelated-user execution.',
                    acceptance='host', targets=[])
    obligations = {'002': [original]}
    calls = []
    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        calls.append(state['task_id'])
        assert state['consolidation_obligations'] == obligations
        if state['task_id'] == '002':
            prompt = (run / 'prompt.txt').read_text()
            assert original['scope'] in prompt and original['brief'] in prompt
        complete(rig.plan, state['task_id'])
        return response(state)
    monkeypatch.setattr(workflow, 'execute', execute)
    TaskBudget(rig.run).initialize(1)
    assert rig.worker(dict(phase='complete', task_sessions=0, total_sessions=0,
                           consolidation_obligations=obligations)) == 0
    assert calls == ['001']
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    recovered = workflow.initial_state(rig.plan, rig.spec, rig.run.parent)
    assert recovered['consolidation_obligations'] == obligations
    restarted = rig.root / 'restarted'
    restarted.mkdir()
    TaskBudget(restarted).initialize(1)
    owner = os.open(restarted / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
    assert workflow.worker(rig.root, restarted, owner, rig.spec, recovered) == 0
    assert calls == ['001', '002']


@pytest.mark.parametrize('destination', ['001', '003'])
def test_additional_consolidation_preserves_earlier_original_obligations(consolidated_plan, destination):
    scene = consolidated_plan
    checkpoint = scene.run / 'checkpoint.json'
    state = json.loads(checkpoint.read_text())
    original = dict(task_id='older-source', scope='Original retained obligation',
                    brief='Require both complete matching histories and cleanup.',
                    acceptance='installed', targets=['Ubuntu'] if destination == '001' else ['Ubuntu', 'Fedora'])
    state['consolidation_obligations'] = {destination: [original]}
    workflow.launcher.atomic(checkpoint, state)
    workflow.reconcile_plan(scene.root, scene.spec, scene.run.name,
                            merge_tasks=['002=001'], base=scene.base)
    updated = json.loads(checkpoint.read_text())
    assert updated['consolidation_obligations'][destination][0] == original
    assert updated['consolidation_obligations']['001'][-1]['task_id'] == '002'


def test_future_merged_brief_cannot_drop_acceptance_before_selection(consolidated_plan):
    scene = consolidated_plan
    workflow.reconcile_plan(scene.root, scene.spec, scene.run.name,
                            merge_tasks=['002=001'], base=scene.base)
    checkpoint = scene.run / 'checkpoint.json'
    state = json.loads(checkpoint.read_text())
    state['suspended_tasks'].pop('001')  # The destination has not started on this branch.
    workflow.launcher.atomic(checkpoint, state)
    brief = scene.root / 'docs/combined.md'
    brief.write_text(brief.read_text().replace('Ubuntu, Fedora', 'Ubuntu'))
    with pytest.raises(ValueError, match='original acceptance kind and all targets'):
        workflow.initial_state(scene.plan, scene.spec, scene.run.parent)


def peer_change(fixture, path, content):
    (fixture.peer / path).write_text(content)
    fixture.git('add', '--', path, cwd=fixture.peer)
    fixture.git('commit', '-qm', 'Upstream change', cwd=fixture.peer)
    fixture.git('push', '-q', cwd=fixture.peer)


def test_pull_preserves_unrelated_index_worktree_and_untracked_work(git_plan):
    f = git_plan
    f.git('config', 'merge.autoStash', 'true')
    (f.root / 'unrelated.py').write_text('staged unrelated\n')
    f.git('add', '--', 'unrelated.py')
    (f.root / 'unrelated.py').write_text('unstaged unrelated too\n')
    (f.root / 'untracked.txt').write_text('private untracked\n')
    (f.root / 'task.py').write_text('task work\n')
    before = launcher_git.worktree_snapshot(f.root)
    index = f.git('ls-files', '--stage', '-z').stdout
    launcher_git.pull_before_commit(f.root, f.run, {})
    assert launcher_git.worktree_snapshot(f.root) == before
    assert f.git('ls-files', '--stage', '-z').stdout == index
    assert f.git('stash', 'list').stdout == ''


@pytest.mark.parametrize('interrupted', [False, True])
def test_changed_upstream_requires_revalidation_even_after_interrupted_pull(git_plan, interrupted):
    f = git_plan
    peer_change(f, 'shared.py', 'new upstream\n')
    state = {}

    def git(root, *args, **kwargs):
        result = launcher_git.git_output(root, *args, **kwargs)
        if interrupted and args[0] == 'pull':
            raise OSError('private interruption after pull')
        return result

    with pytest.raises(OSError if interrupted else launcher_git.GitReconciliationRequired):
        launcher_git.pull_before_commit(f.root, f.run, state, git=git)
    saved = json.loads((f.run / 'checkpoint.json').read_text())
    assert saved['pull_intent']['head'] != f.git('rev-parse', 'HEAD').stdout.strip()
    with pytest.raises(launcher_git.GitReconciliationRequired, match='HEAD'):
        launcher_git.pull_before_commit(f.root, f.run, saved)
    assert f.git('log', '-1', '--format=%s').stdout.strip() == 'Upstream change'


def test_dirty_overlap_requests_scoped_reconciliation_without_autostash(git_plan):
    f = git_plan
    f.git('config', 'merge.autoStash', 'true')
    (f.root / 'task.py').write_text('local task work\n')
    (f.root / 'unrelated.py').write_text('unrelated staged work\n')
    f.git('add', '--', 'unrelated.py')
    peer_change(f, 'task.py', 'upstream task work\n')
    index = f.git('ls-files', '--stage', '-z').stdout
    before = launcher_git.worktree_snapshot(f.root)
    head = f.git('rev-parse', 'HEAD').stdout
    with pytest.raises(launcher_git.GitReconciliationRequired, match='scoped reconciliation'):
        launcher_git.pull_before_commit(f.root, f.run, {})
    assert f.git('rev-parse', 'HEAD').stdout == head
    assert launcher_git.worktree_snapshot(f.root) == before
    assert f.git('ls-files', '--stage', '-z').stdout == index
    assert f.git('stash', 'list').stdout == ''


@pytest.mark.parametrize('change', ['branch', 'upstream', 'missing-identity'])
def test_pending_commit_recovery_preserves_branch_and_upstream_identity(git_plan, change):
    f = git_plan
    state = {}
    launcher_git.pull_before_commit(f.root, f.run, state)
    (f.root / 'task.py').write_text('accepted task\n')
    paths = launcher_git.stage_task(f.root, ['task.py'])
    launcher_git.finish_commit(f.root, f.run, state, paths, 'TA: Completed task 001')
    assert 'commit_intent' in state
    if change == 'branch':
        upstream = state['pull_intent']['upstream']
        f.git('switch', '-qc', 'other-branch')
        f.git('branch', '--set-upstream-to', upstream)
    elif change == 'upstream':
        branch = state['pull_intent']['branch']
        f.git('remote', 'add', 'other-origin', str(f.remote))
        f.git('fetch', '-q', 'other-origin')
        f.git('branch', '--set-upstream-to', f'other-origin/{branch}')
    else:
        state.pop('pull_intent')
    with pytest.raises(ValueError, match='branch or upstream changed|no retained branch/upstream identity'):
        launcher_git.pull_before_commit(f.root, f.run, state)
    assert f.git('rev-parse', 'HEAD', cwd=f.remote).stdout != f.git('rev-parse', 'HEAD').stdout


def test_unfinished_merge_without_unmerged_paths_requests_coordinator(git_plan):
    f = git_plan
    (f.root / 'task.py').write_text('local committed history\n')
    f.git('add', '--', 'task.py')
    f.git('commit', '-qm', 'Local history')
    peer_change(f, 'shared.py', 'upstream shared history\n')
    f.git('fetch', '-q')
    f.git('merge', '--no-ff', '--no-commit', '@{upstream}')
    assert f.git('diff', '--name-only', '--diff-filter=U').stdout == ''
    with pytest.raises(launcher_git.GitReconciliationRequired, match='reconciliation'):
        launcher_git.pull_before_commit(f.root, f.run, {})
    assert f.git('rev-parse', '--verify', 'MERGE_HEAD').returncode == 0
    assert f.git('log', '-1', '--format=%s').stdout.strip() == 'Local history'


def test_reconciled_master_cannot_rebind_retained_queue(rig):
    state = state_for(rig.plan, git_reconciliation=dict(reason='Resolve queue merge.'))
    complete(rig.plan, '001')
    shutil.copy2(rig.root / rig.plan.queue, rig.root / 'docs/other-queue.md')
    master = rig.root / rig.plan.path
    master.write_text(master.read_text().replace('(queue.md)', '(other-queue.md)'))
    with pytest.raises(ValueError, match='master plan queue changed'):
        workflow.validate_result(rig.plan, state, response(state))


def test_git_reconciliation_cannot_suspend_task_for_another_prerequisite(rig):
    state = state_for(rig.plan, git_reconciliation=dict(reason='Resolve upstream changes.'))
    with pytest.raises(ValueError, match='Git reconciliation'):
        workflow.validate_result(rig.plan, state, response(state, 'prerequisite_required'))


@pytest.mark.parametrize('mode', ['fast-forward', 'merge-conflict'])
def test_upstream_reconciliation_resolves_and_revalidates_before_commit_and_push(git_plan, monkeypatch, mode):
    f = git_plan
    if mode == 'merge-conflict':
        f.git('config', 'pull.ff', 'only')
        (f.root / 'shared.py').write_text('local shared history\n')
        f.git('add', '--', 'shared.py')
        f.git('commit', '-qm', 'Local shared history')
    peer_change(f, 'shared.py', 'upstream shared history\n')
    state = state_for(f.plan, task_sessions=1, total_sessions=1)
    (f.root / 'task.py').write_text('completed task\n')
    complete(f.plan, '001')
    state['pending_completion'] = response(state)
    state['pending_completion']['stage_paths'].append('task.py')
    TaskBudget(f.run).initialize(1)
    calls = []
    monkeypatch.setattr(workflow.launcher, 'finish_nested', lambda *_: None)
    monkeypatch.setattr(workflow.signal, 'signal', lambda *_: None)

    def reconcile(root, spec, run, owner):
        saved = json.loads((run / 'checkpoint.json').read_text())
        calls.append(saved['task_id'])
        assert saved['git_reconciliation']['accepted_result']['status'] == 'task_complete'
        assert TaskBudget(run).read()['completed'] == 0
        prompt = (run / 'prompt.txt').read_text()
        assert 'Re-run acceptance' in prompt and 'Do not stash unrelated work' in prompt
        if mode == 'merge-conflict':
            assert f.git('diff', '--name-only', '--diff-filter=U').stdout.strip() == 'shared.py'
            (root / 'shared.py').write_text('local and upstream shared history\n')
            f.git('add', '--', 'shared.py')
            f.git('commit', '--no-edit')
        result = response(saved)
        result['checks'][0]['evidence'] = 'Revalidated the merged candidate and owned cleanup.'
        result['stage_paths'].append('task.py')
        return result

    monkeypatch.setattr(workflow, 'execute', reconcile)
    owner = os.open(f.run / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
    assert workflow.worker(f.root, f.run, owner, workflow.PlanWorkflow('fixture', f.plan.path), state) == 0
    assert calls == ['001']
    assert TaskBudget(f.run).read()['completed'] == 1
    assert f.git('log', '-1', '--format=%s').stdout.strip() == 'TA: Completed task 001'
    assert f.git('rev-parse', 'HEAD', cwd=f.remote).stdout == f.git('rev-parse', 'HEAD').stdout
    assert f.git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').stdout.splitlines() == [
        'docs/plan.md', 'docs/queue.md', 'task.py']
    assert f.plan.next_task().id == '002'


def test_conflicted_queue_restarts_from_retained_identity_then_rechecks_guards(rig, monkeypatch):
    state = state_for(rig.plan, phase='recover', plan_queue=rig.plan.queue,
                      git_reconciliation=dict(reason='Resolve upstream queue conflicts.'))
    (rig.root / rig.plan.path).write_text('<<<<<<< HEAD\n=======\n>>>>>>> upstream\n')
    previous = rig.root / 'previous'
    previous.mkdir()
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    plan = workflow.load_plan(rig.root, rig.plan.path, state)
    recovered = workflow.initial_state(plan, rig.spec, rig.root)
    assert recovered['git_reconciliation'] == state['git_reconciliation']

    def resolve(root, spec, run, owner):
        complete(rig.plan, '001')
        return response(recovered)

    monkeypatch.setattr(workflow, 'execute', resolve)
    assert rig.worker(recovered) == 0
    assert TaskBudget(rig.run).read()['completed'] == 1


@pytest.mark.parametrize('mode', ['none', 'question'])
def test_nonchat_shared_panes_resize_and_scroll_without_composer(tmp_path, mode):
    terminal = Terminal(120, 30)
    display = TaskDisplay(terminal, run=tmp_path, input_mode=mode, terminal_size=lambda: terminal.size)
    try:
        display.task_info = dict(explanation='\n'.join(f'Purpose {n}' for n in range(60)), status='Reviewing.')
        display.update([dict(key='count', pinned=True, lines=['\033[32mTasks: 4/13/17\033[0m']),
                        dict(key='task', lines=['Current task', 'Current session'])], [])
        display.write('Execution output\n')
        visible = terminal.visible()
        assert visible.splitlines()[0].split('│')[0].strip() == 'Current task'
        assert 'Tasks: 4/13/17' not in visible
        assert 'Execution output' in visible and 'Current task' in visible
        assert 'Chat' not in visible and 'Enter: send' not in visible
        # Pane controls work immediately; m remains a selection-mode shortcut.
        assert display.mouse_capture
        display.handle_input(f'\x1b[<0;{display.top_divider_column};1M'.encode())
        display.handle_input(b'\x1b[<32;75;1M\x1b[<0;75;1m')
        assert display.ratio == 74 / 118
        assert display.top_divider_column == display.divider_column
        row, divider = display.top_height + 3, display.divider_column
        for fragment in (b'\x1b[<0;', f'{divider};{row}M'.encode()):
            display.handle_input(fragment)
        display.handle_input(f'\x1b[<32;61;{row}M\x1b[<0;61;{row}m'.encode())
        assert display.ratio == 60 / 118
        assert display.top_divider_column == display.divider_column
        display.handle_input(f'\x1b[<65;100;{display.summary_bottom + 2}M'.encode())
        assert display.offsets['info'] > 0
        assert display.editor.text == ''
        display.handle_input(b'm')
        assert not display.mouse_capture
        display.handle_input(b'\x1bOQ')
        assert display.mouse_capture
    finally:
        display.close()


def test_plan_totals_refresh_whole_queue_without_output_or_pointer_updates(tmp_path, monkeypatch):
    # This fixture is an ANSI terminal even when the launcher inherits TERM=dumb.
    monkeypatch.setenv('TERM', 'xterm')
    plan = prepare(tmp_path, count=4)
    run = tmp_path / 'run'
    run.mkdir()
    TaskBudget(run).initialize(1, remaining=4)
    terminal = Terminal(120, 30)
    view = WorkflowView(totals=lambda: plan_totals(tmp_path, plan.path))
    display = view.display(terminal, run)
    display.terminal_size = lambda: terminal.size
    queue = tmp_path / plan.queue
    try:
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 0/4/4' in terminal.visible()
        # Editing the checkbox before acceptance/Git close-out grants no credit.
        queue.write_text(queue.read_text().replace('| [ ] | 001 |', '| [x] | 001 |'))
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 0/4/4' in terminal.visible()
        assert display.runtime_tasks['lines'] == ['Tasks: 0/1/1']
        TaskBudget(run).complete()
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 1/3/4' in terminal.visible()
        assert display.runtime_tasks['lines'] == ['Tasks: 1/0/1']
        row = display.previous[0]
        start = row.plain.index('Total Tasks: ') + len('Total Tasks: ')
        assert row.get_style_at_offset(display.console, start).color.name == 'green'
        assert row.get_style_at_offset(display.console, start + 2).color.name == '#808080'
        assert row.get_style_at_offset(display.console, start + 4).color.name == 'default'
        valid = queue.read_text()
        queue.write_text('Partial rewrite')
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 1/3/4' in terminal.visible()
        queue.write_text(valid.replace('| [ ] | 002 |', '| [x] | 002 |'))
        TaskBudget(run).complete()
        TaskBudget(run).set_limit(0)
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 2/2/4' in terminal.visible()
        queue.write_text(queue.read_text().replace('## Deferred future work',
                         '| [ ] | 005 | [Task 005](005.md) | — | added task |\n## Deferred future work'))
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 2/3/5' in terminal.visible()
        queue.write_text(queue.read_text().replace('| [ ] |', '| [x] |'))
        for _ in range(3):
            TaskBudget(run).complete()
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 5/0/5' in terminal.visible()
    finally:
        display.close()


@pytest.mark.parametrize('completed_before', [0, 1])
@pytest.mark.parametrize('retained_queue', [False, True])
def test_default_run_and_whole_plan_share_accepted_completion_snapshot(
        tmp_path, monkeypatch, completed_before, retained_queue):
    monkeypatch.setenv('TERM', 'xterm')
    plan = prepare(tmp_path, count=64)
    if completed_before:
        complete(plan, '001')
    run = tmp_path / 'run'
    run.mkdir()
    budget = TaskBudget(run)
    budget.initialize(1, remaining=64 - completed_before)
    if retained_queue:
        workflow.launcher.atomic(run / 'checkpoint.json', {'queue_before': plan.state()})
    view = WorkflowView(totals=lambda: plan_totals(tmp_path, plan.path))

    def observe():
        terminal = Terminal(120, 30)
        display = view.display(terminal, run)
        display.terminal_size = lambda: terminal.size
        return terminal, display

    terminal, display = observe()
    try:
        # Acceptance/Git failure can leave a checked row with no budget credit.
        complete(plan, f'{completed_before + 1:03}')
        display.refresh_chat()
        display.update(task_progress(run, []), [])
        assert display.runtime_tasks['lines'] == ['Tasks: 0/1/1']
        assert f'Total Tasks: {completed_before}/{64 - completed_before}/64' in terminal.visible()
        # Even if completion lands between refresh and update, render one snapshot.
        budget.complete()
        display.update(task_progress(run, []), [])
        assert display.runtime_tasks['lines'] == ['Tasks: 0/1/1']
        assert f'Total Tasks: {completed_before}/{64 - completed_before}/64' in terminal.visible()
        display.refresh_chat()
        display.draw()  # Input/output redraws before the next controller update.
        assert display.runtime_tasks['lines'] == ['Tasks: 1/0/1']
        assert f'Total Tasks: {completed_before + 1}/{63 - completed_before}/64' in terminal.visible()
    finally:
        display.close()
    # A new observer reads the retained budget without resetting accepted history.
    total = 64
    if retained_queue:
        queue = tmp_path / plan.queue
        queue.write_text(queue.read_text().replace('## Deferred future work',
            '| [ ] | 065 | [Prerequisite](065.md) | — | added task |\n## Deferred future work'))
        total += 1
    terminal, display = observe()
    try:
        display.refresh_chat()
        display.update(task_progress(run, []), [])
        assert display.runtime_tasks['lines'] == ['Tasks: 1/0/1']
        assert f'Total Tasks: {completed_before + 1}/{total - completed_before - 1}/{total}' in terminal.visible()
        budget.set_limit(0)
        display.refresh_chat()
        display.draw()
        assert display.runtime_tasks['lines'] == [f'Tasks: 1/{total - completed_before - 1}/{total - completed_before}']
        assert f'Total Tasks: {completed_before + 1}/{total - completed_before - 1}/{total}' in terminal.visible()
    finally:
        display.close()


def test_e2e_view_reads_canonical_plan_totals(monkeypatch):
    import launcher_view
    import write_e2e
    calls = []
    monkeypatch.setattr(launcher_view, 'plan_totals',
                        lambda root, path: calls.append((root, path)) or (3, 7, 10))
    assert view_for('write-e2e').totals() == (3, 7, 10)
    assert calls == [(Path(launcher_view.__file__).resolve().parent.parent, write_e2e.PLAN)]


def test_shared_counter_updates_are_preserved_in_plain_output(tmp_path):
    import io

    budget = TaskBudget(tmp_path)
    budget.initialize(1, remaining=64)
    output = io.StringIO()
    display = WorkflowView(totals=lambda: (0, 64, 64)).display(output, tmp_path)
    try:
        display.refresh_chat()
        display.update([], [])
        budget.complete()
        display.refresh_chat()
        display.update([], [])
        assert output.getvalue() == 'Tasks: 0/1/1\nTasks: 1/0/1\n'
    finally:
        display.close()


def test_configured_plan_model_and_bounded_sol_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow.launcher.shutil, 'which', lambda _: '/private/codex')
    spec = workflow.PlanWorkflow('fixture-plan', effort='xhigh')
    command = workflow.session_command(tmp_path, spec, tmp_path)
    config = tomllib.loads('\n'.join(command[i + 1] for i, arg in enumerate(command) if arg == '-c'))
    assert command[command.index('--model') + 1] == 'gpt-6.1-sol'
    assert config['model_reasoning_effort'] == 'xhigh'
    assert config['features']['fast_mode'] is False
    assert config['agents']['max_depth'] == 1
    for name, effort, sandbox in [('plan_monitor', 'low', 'read-only'), ('plan_worker', 'medium', 'workspace-write')]:
        role = tomllib.loads(Path(config['agents'][name]['config_file']).read_text())
        assert role['model'] == 'gpt-6.1-sol' and role['model_reasoning_effort'] == effort
        assert role['sandbox_mode'] == sandbox and role['approval_policy'] == 'never'
        assert role['features']['multi_agent'] is False and role['agents']['enabled'] is False
    assert workflow.PlanWorkflow('custom').effort == 'high'


def test_relocated_public_cli_checks_plan_without_an_agent(tmp_path):
    prepare(tmp_path)
    tools = tmp_path / 'tools'
    tools.mkdir()
    source = Path(workflow.__file__).parent
    for name in ['execute-plan', 'plan_launcher.py', 'detached_launcher.py', 'execution_plan.py',
                 'document_checks.py', 'launcher_git.py', 'launcher_progress.py', 'launcher_question.py',
                 'launcher_runtime.py', 'test_storage.py', 'test_retention.py', 'test_input_transfer.py',
                 'plan_evidence.py', 'plan_evidence_recovery.py', 'evidence_bundle.py']:
        shutil.copy2(source / name, tools / name)
    result = subprocess.run([sys.executable, '-B', str(tools / 'execute-plan'), '--plan', 'docs/plan.md', '--check'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(plan='docs/plan.md', queue='docs/queue.md',
                                           next_task='001', remaining=2, model='gpt-6.1-sol', effort='high')
    assert not (tmp_path / 'output').exists()


def test_worker_entry_uses_checkpoint_published_after_command_construction(tmp_path):
    run = tmp_path / 'run'
    run.mkdir(mode=0o700)
    workflow.launcher.atomic(run / 'checkpoint.json',
                             {'source': 'carried exact proof', 'recovery': 'x' * (256 * 1024)})
    source = Path(workflow.__file__).read_text()
    marker = "if __name__ == '__main__':"
    observer = ("def worker(root, run, owner, spec, state):\n"
                "    assert state['source'] == 'carried exact proof', state\n"
                "    assert len(state['recovery']) == 256 * 1024\n"
                "    return 0\n\n")
    # Keep the real private entry and argument parser; substitute only its
    # process body so no model, Git transaction or shared owner is started.
    entry = tmp_path / 'entry.py'
    entry.write_text('import sys\nsys.path.insert(0, '
                     + repr(str(Path(workflow.__file__).parent)) + ')\n'
                     + source.replace(marker, observer + marker, 1))
    command = [sys.executable, '-B', str(entry), '--worker', str(tmp_path), str(run), '-1',
               json.dumps(dict(name='fixture-plan', plan='docs/plan.md'))]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


def test_plan_namespace_registers_and_cancels_only_recorded_nested_owner(tmp_path, monkeypatch):
    import detached_launcher as launcher
    from test_storage import directory
    namespace = directory('plans', root=tmp_path) / ('a' * 64)
    namespace.mkdir(mode=0o700)
    parent = namespace / ('b' * 32)
    parent.mkdir(mode=0o700)
    launcher.atomic(namespace / 'current.json', dict(run=parent.name))
    child = directory('sessions-host', root=tmp_path) / ('c' * 32)
    child.mkdir(mode=0o700)
    unrelated = child.parent / ('d' * 32)
    unrelated.mkdir(mode=0o700)
    monkeypatch.setenv(launcher.WORKFLOW_DIRECTORY, str(parent))
    ownership = iter([True, True, False, True])
    monkeypatch.setattr(launcher, 'busy', lambda _: next(ownership))
    with launcher.nested_operation(tmp_path, child):
        record, = json.loads((parent / 'nested.json').read_text())
        assert record == dict(path=str(child), device=child.stat().st_dev, inode=child.stat().st_ino)
    assert launcher.finish_nested(tmp_path, parent) is True
    assert (child / 'cancel').exists()
    assert not (unrelated / 'cancel').exists()
    with pytest.raises(ValueError, match='no longer accepting'):
        with launcher.nested_operation(tmp_path, unrelated):
            pytest.fail('closed workflow admitted another child')


def test_backend_clock_is_published_before_spawn_preserved_on_attach_and_reset_on_restart(tmp_path, monkeypatch):
    import detached_launcher as launcher
    clock = [1000.0]
    active = [False]
    publications = []
    monkeypatch.setattr(launcher.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(launcher, 'busy', lambda _: active[0])

    def spawn(*args, **kwargs):
        from test_storage import directory
        publications.append(json.loads((directory('fix-tests', root=tmp_path) / 'current.json').read_text()))

    monkeypatch.setattr(launcher.subprocess, 'Popen', spawn)
    command = lambda run, owner: ['private-worker-double']
    run, started = launcher.select(tmp_path, 'fix-tests', command)
    assert started
    assert publications == [dict(run=run.name, started_at=publications[0]['started_at'],
                                 started_monotonic=1000.0)]
    record = (run.parent / 'current.json').read_bytes()
    active[0] = True
    clock[0] += 720
    assert launcher.select(tmp_path, 'fix-tests', command) == (run, False)
    assert (run.parent / 'current.json').read_bytes() == record
    assert len(publications) == 1
    active[0] = False
    next_run, started = launcher.select(tmp_path, 'fix-tests', command)
    assert started and next_run != run
    assert publications[-1]['started_monotonic'] == 1720.0


@pytest.fixture(params=[False, True], ids=['legacy-registration', 'resumable-registration'])
def pending_plan_start(tmp_path, monkeypatch, request):
    import detached_launcher as launcher
    import test_retention as retention
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    spawned = []
    monkeypatch.setattr(launcher.subprocess, 'Popen', lambda *args, **kwargs: spawned.append(args))
    namespace = 'e' * 64

    def start(run):
        launcher.atomic(run / 'checkpoint.json', {'exact': 'source accepted work'})
        (run / 'accepted-proof').write_text('exact accepted proof')

    source, _ = launcher.select(tmp_path, 'plans', lambda *_: ['worker-double'],
                                namespace=namespace, resumable_start=request.param, on_start=start)
    attempts = []

    def command(run, owner):
        assert launcher.current_run(run.parent) == source
        assert json.loads((source / 'checkpoint.json').read_text()) == {'exact': 'source accepted work'}
        attempts.append(run)
        return ['worker-double']

    def fail(run):
        launcher.atomic(run / 'checkpoint.json', {'partial': 'interrupted carry'})
        raise OSError('carry interrupted')

    def invoke(callback=fail):
        return launcher.select(tmp_path, 'plans', command, namespace=namespace,
                               resumable_start=True, on_start=callback)

    return SimpleNamespace(launcher=launcher, retention=retention, root=tmp_path,
                           source=source, attempts=attempts, spawned=spawned, invoke=invoke,
                           legacy=not request.param, namespace=namespace)


def test_resumable_start_retries_same_registered_run_without_rotating_source(pending_plan_start):
    scene = pending_plan_start
    source, launcher = scene.source, scene.launcher
    current = (source.parent / 'current.json').read_bytes()
    for _ in range(3):
        with pytest.raises(OSError, match='carry interrupted'):
            scene.invoke()
        assert (source.parent / 'current.json').read_bytes() == current
        assert (source / 'accepted-proof').read_text() == 'exact accepted proof'
    pending = json.loads((source.parent / 'pending-start.json').read_text())
    destination = source.parent / pending['run']
    assert scene.attempts == [destination] * 3
    journal = json.loads((source.parent / 'retention/current.json').read_text())
    assert [entry['run'] for entry in [*journal['history'], journal]] == [
        pending['source_retention_run'], destination.name]
    assert pending['source_allocation']['path'] == str(source)
    if scene.legacy:
        assert pending['source_retention_run'] != source.name
    else:
        assert pending['source_retention_run'] == source.name

    def complete(run):
        assert run == destination
        launcher.atomic(run / 'checkpoint.json', json.loads((source / 'checkpoint.json').read_text()))
        (run / 'accepted-proof').write_bytes((source / 'accepted-proof').read_bytes())

    assert scene.invoke(complete) == (destination, True)
    assert not (source.parent / 'pending-start.json').exists()
    assert launcher.current_run(source.parent) == destination
    assert source.exists() and (destination / 'accepted-proof').read_text() == 'exact accepted proof'
    assert len(scene.spawned) == 2


@pytest.mark.parametrize('defect', ['marker', 'directory', 'foreign-registration', 'missing-journal'])
def test_resumable_start_refuses_replaced_pending_identity(pending_plan_start, defect):
    scene = pending_plan_start
    with pytest.raises(OSError):
        scene.invoke()
    path = scene.source.parent / 'pending-start.json'
    pending = json.loads(path.read_text())
    destination = scene.source.parent / pending['run']
    journal_path = scene.source.parent / 'retention/current.json'
    if defect == 'marker':
        pending['inode'] += 1
        scene.launcher._publish_start(path, pending)
    elif defect == 'directory':
        destination.rename(destination.with_name(destination.name + '-replaced'))
        destination.mkdir(mode=0o700)
    elif defect == 'foreign-registration':
        journal = json.loads(journal_path.read_text())
        journal['paths'].append(journal['history'][-1]['paths'][0])
        scene.launcher.atomic(journal_path, journal)
    else:
        journal_path.unlink()
    original = journal_path.read_bytes() if journal_path.exists() else None
    with pytest.raises(ValueError):
        scene.invoke()
    assert scene.launcher.current_run(scene.source.parent) == scene.source
    assert (scene.source / 'accepted-proof').read_text() == 'exact accepted proof'
    assert (journal_path.read_bytes() if journal_path.exists() else None) == original


def test_pending_partial_carry_over_budget_refuses_before_any_retention_prune(pending_plan_start, monkeypatch):
    scene = pending_plan_start
    with pytest.raises(OSError):
        scene.invoke()
    destination = scene.attempts[-1]
    journal = scene.source.parent / 'retention/current.json'
    original = journal.read_bytes()
    real_size = scene.retention.allocation_bytes
    monkeypatch.setattr(scene.retention, 'allocation_bytes', lambda record:
        scene.retention.MAX_RETAINED_BYTES if record['path'] == str(destination) else real_size(record))
    with pytest.raises(ValueError, match='budget; source evidence preserved'):
        scene.invoke()
    assert journal.read_bytes() == original
    assert scene.source.exists() and destination.exists()


def test_exact_pending_registration_can_recover_an_interrupted_retention_session(pending_plan_start):
    scene = pending_plan_start
    with pytest.raises(OSError):
        scene.invoke()
    journal = scene.source.parent / 'retention/current.json'
    value = json.loads(journal.read_text())
    value['finished'] = False
    scene.launcher.atomic(journal, value)
    journal.chmod(0o600)
    destination = scene.attempts[-1]
    assert scene.invoke(lambda run: None) == (destination, True)
    assert (scene.source.parent / 'retention' / ('interrupted-' + destination.name + '.json')).exists()
    assert scene.source.exists()


def test_ready_current_publication_never_spawns_a_duplicate_pending_worker(pending_plan_start, monkeypatch):
    scene = pending_plan_start
    clear = scene.launcher._clear_start
    monkeypatch.setattr(scene.launcher, '_clear_start',
                        lambda *_: (_ for _ in ()).throw(OSError('interrupted ready publication')))
    with pytest.raises(OSError, match='ready publication'):
        scene.invoke(lambda run: None)
    destination = scene.attempts[-1]
    assert scene.launcher.current_run(scene.source.parent) == destination
    assert len(scene.spawned) == 1
    monkeypatch.setattr(scene.launcher, '_clear_start', clear)
    # This branch verifies and retires the ready marker; command/on_start must
    # not be called against the already published destination.
    assert scene.invoke(lambda run: pytest.fail('duplicated startup')) == (destination, False)
    assert len(scene.spawned) == 1
    assert not (scene.source.parent / 'pending-start.json').exists()


def test_nonresumable_caller_cannot_ignore_a_pending_start(pending_plan_start):
    scene = pending_plan_start
    with pytest.raises(OSError):
        scene.invoke()
    journal = scene.source.parent / 'retention/current.json'
    original = journal.read_bytes()
    with pytest.raises(ValueError, match='requires its resumable controller'):
        scene.launcher.select(scene.root, 'plans', lambda *_: pytest.fail('allocated another run'),
                              namespace=scene.namespace)
    assert journal.read_bytes() == original
    assert scene.launcher.current_run(scene.source.parent) == scene.source
    assert len(set(scene.attempts)) == 1


@pytest.mark.parametrize('limit', [0, -3, 8])
def test_public_detached_adapter_exhausts_private_queue_with_app_server_double(tmp_path, limit):
    """Exercise real worker serialization and supervision without a model or VM."""
    import time
    import detached_launcher as launcher
    from test_storage import directory

    plan = prepare(tmp_path)
    queue_estimates(plan)
    tools = tmp_path / 'tools'
    tools.mkdir()
    source = Path(workflow.__file__).parent
    names = [
        'execute-plan', 'plan_launcher.py', 'execution_plan.py', 'document_checks.py', 'detached_launcher.py',
        'launcher_git.py', 'launcher_runtime.py', 'launcher_progress.py',
        'launcher_question.py', 'launcher_view.py', 'launcher_display.py',
        'launcher_chat.py', 'launcher_render.py', 'watch_output.py', 'vm_selection.py',
        'test_storage.py', 'test_retention.py', 'test_input_transfer.py',
        'plan_evidence.py', 'plan_evidence_recovery.py', 'evidence_bundle.py',
        'plan_response.schema.json', 'plan_monitor.toml', 'plan_worker.toml',
    ]
    for name in names:
        shutil.copy2(source / name, tools / name)
    integration = tmp_path / 'tests/integration'
    integration.mkdir(parents=True)
    shutil.copy2(source.parent / 'tests/integration/vm_config.py', integration / 'vm_config.py')
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True, timeout=10)
    subprocess.run(['git', 'config', 'user.name', 'Launcher test'], cwd=tmp_path, check=True, timeout=10)
    subprocess.run(['git', 'config', 'user.email', 'launcher@example.invalid'], cwd=tmp_path, check=True, timeout=10)
    remote = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True, timeout=10)
    (tmp_path / '.git/info/exclude').write_text('output/\nbin/\nscript.json\ncalls.jsonl\nagent-ready-*\n')
    subprocess.run(['git', 'add', '--', 'docs', 'tools', 'tests'], cwd=tmp_path, check=True, timeout=10)
    subprocess.run(['git', 'commit', '-qm', 'Private baseline'], cwd=tmp_path, check=True, timeout=10)
    subprocess.run(['git', 'remote', 'add', 'origin', str(remote)], cwd=tmp_path, check=True, timeout=10)
    subprocess.run(['git', 'push', '-qu', 'origin', 'HEAD'], cwd=tmp_path, check=True, timeout=10)
    private_bin = tmp_path / 'bin'
    private_bin.mkdir()
    codex = private_bin / 'codex'
    child_double = source.parent / 'tests/support/write_e2e_child.py'
    codex.write_text(f'#!{sys.executable}\nimport runpy\n'
                     f'runpy.run_path({str(child_double)!r}, run_name="__main__")\n')
    codex.chmod(0o700)
    queue = (tmp_path / plan.queue).read_text()
    first_queue = queue.replace('| [ ] | 001 |', '| [x] | 001 |').replace(
        'finite scope 001 | 15–30 min', 'finite scope 001 | Scoped acceptance passed')
    final_queue = first_queue.replace('| [ ] | 002 |', '| [x] | 002 |').replace(
        'finite scope 002 | 15–30 min', 'finite scope 002 | Scoped acceptance passed')
    steps = []
    for identity, updated_queue, pointer in [
        ('001', first_queue, 'Next task: **002 — Next**.'),
        ('002', final_queue, 'Next task: none.'),
    ]:
        steps.append(dict(result=response(dict(task_id=identity)), writes={
            plan.queue: updated_queue,
            plan.path: 'Task queue: [Queue](queue.md).\n' + pointer + '\n',
        }))
    (tmp_path / 'script.json').write_text(json.dumps(steps))
    environment = {name: value for name, value in os.environ.items()
                   if not name.startswith(('CODEX_', 'ONPC_TEST_', 'ONPC_WORKFLOW_'))}
    private_home = tmp_path / 'home'
    private_home.mkdir()
    environment.update(PATH=str(private_bin) + ':/usr/bin:/bin', HOME=str(private_home),
                       CODEX_HOME=str(private_home / '.codex'),
                       XDG_CONFIG_HOME=str(private_home / '.config'),
                       XDG_CACHE_HOME=str(private_home / '.cache'),
                       CODEX_THREAD_ID='parent-thread-must-not-leak', PYTHONDONTWRITEBYTECODE='1')
    namespace = directory('plans', root=tmp_path) / plan.namespace
    # The public observer is explicitly spawned/reaped here. Its detached worker
    # is cancelled only through its exact recorded run and ownership lock; no PID
    # discovery or process-group signalling is used during fixture cleanup.
    observer = subprocess.Popen([sys.executable, '-B', str(tools / 'execute-plan'),
                                 '--plan', plan.path, '--tasks', str(limit)], cwd=tmp_path,
                                env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    owner_released = True
    try:
        output, errors = observer.communicate(timeout=30)
    finally:
        run = launcher.current_run(namespace) if namespace.exists() else None
        if run is not None:
            with launcher.lock(namespace / 'owner') as owner:
                if launcher.busy(owner):
                    (run / 'cancel').touch(mode=0o600)
                deadline = time.monotonic() + 20
                while launcher.busy(owner) and time.monotonic() < deadline:
                    time.sleep(.02)
                owner_released = not launcher.busy(owner)
        if observer.poll() is None:
            observer.kill()  # Only this test's explicitly spawned observer.
        observer.communicate(timeout=5)
    assert owner_released, 'recorded detached worker did not finish owned cancellation'
    assert observer.returncode == 0, output + errors
    assert run is not None
    assert json.loads((run / 'result.json').read_text()) == dict(status=0, tasks=2)
    assert 'queue complete' in (run / 'handoff.txt').read_text()
    calls = [json.loads(line) for line in (tmp_path / 'calls.jsonl').read_text().splitlines()]
    assert len(calls) == 2
    assert [call['turn_start']['input'][0]['text'].splitlines()[0] for call in calls] == [
        'Implement only task 001: Task 001.', 'Implement only task 002: Task 002.']
    assert all(call['thread'] is None for call in calls)
    assert all(call['thread_start']['model'] == 'gpt-6.1-sol' for call in calls)
    assert Plan.load(tmp_path, plan.path).next_task() is None
    with launcher.lock(namespace / 'owner') as owner:
        assert not launcher.busy(owner)
    commits = subprocess.run(['git', 'log', '-2', '--format=%s'], cwd=tmp_path,
                             capture_output=True, text=True, check=True, timeout=10).stdout.splitlines()
    assert commits == ['TA: Completed task 002', 'TA: Completed task 001']
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=tmp_path,
                          capture_output=True, text=True, check=True, timeout=10).stdout
    pushed = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=remote,
                            capture_output=True, text=True, check=True, timeout=10).stdout
    assert pushed == head
    assert subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=tmp_path,
                          capture_output=True, text=True, check=True, timeout=10).stdout == ''
    if limit > 2:
        assert 'only 2 remain' in output


def prerequisite_plan(root):
    plan = prepare(root, count=3)
    complete(plan, '001')
    state = state_for(plan, in_flight=True, handoff='Consumer implementation remains unfinished.')
    queue = root / plan.queue
    added = ('| [ ] | pre-a | [First prerequisite](pre-a.md) | 001 | prerequisite A |\n'
             '| [ ] | pre-b | [Second prerequisite](pre-b.md) | pre-a | prerequisite B |\n')
    text = queue.read_text().replace('| [ ] | 002 |', added + '| [ ] | 002 |')
    queue.write_text(text.replace('| — | finite scope 002', '| pre-b, 001 | finite scope 002'))
    for identity in ('pre-a', 'pre-b'):
        (root / f'docs/{identity}.md').write_text(f'# {identity}\nAcceptance: host\n')
    (root / plan.path).write_text('Task queue: [Queue](queue.md).\nNext task: **pre-a — Prerequisite**.\n')
    return plan, state


def test_prerequisite_repair_recognizes_exact_multilevel_block_without_accepting_consumer(tmp_path):
    plan, state = prerequisite_plan(tmp_path)
    state['consolidation_obligations'] = {'002': [dict(task_id='original', scope='Retained obligation',
        brief='Preserve the full original assertion.', acceptance='host', targets=[])]}
    checkpoint = json.dumps(state, sort_keys=True)
    selected = plan.prerequisite_repair(state)
    assert selected.id == 'pre-a' and selected.brief == tmp_path / 'docs/pre-a.md'
    assert [task.id for task in plan.tasks()] == ['001', 'pre-a', 'pre-b', '002', '003']
    assert plan.state() == {'001': True, 'pre-a': False, 'pre-b': False, '002': False, '003': False}
    assert json.dumps(state, sort_keys=True) == checkpoint
    assert state['task_id'] == '002' and 'unfinished' in state['handoff']
    deferred = workflow.defer_to_prerequisite(plan, state)
    assert deferred['consolidation_obligations'] == state['consolidation_obligations']


def test_prerequisite_repair_allows_only_completed_evidence_destinations(tmp_path):
    plan, state = prerequisite_plan(tmp_path)
    queue = queue_estimates(plan)
    old = '15–30 min; [checks](../output/test-runs/host/old/report.md)'
    text = queue.read_text().replace('finite scope 001 | 15–30 min', f'finite scope 001 | {old}')
    queue.write_text(text)
    # Upgrade this no-Estimate fixture to the literal older snapshot shape.
    for row in state['queue_structure']:
        row.insert(6, old if row[2] == '001' else '15–30 min')
    original = json.dumps(state, sort_keys=True)
    queue.write_text(text.replace('/old/report.md', '/retained/agent-commands.log'))
    assert plan.prerequisite_repair(state).id == 'pre-a'
    assert json.dumps(state, sort_keys=True) == original
    queue.write_text(queue.read_text().replace('[checks]', '[new claim]'))
    assert plan.prerequisite_repair(state) is None
    queue.write_text(text.replace('../output/test-runs/host/old/report.md',
                                  '<completed evidence destination>'))
    assert plan.prerequisite_repair(state) is None


@pytest.mark.parametrize('defect', [
    'unknown', 'skipped', 'reordered', 'changed-status', 'consumer-scope',
    'other-scope', 'extra-unrelated', 'checked-new', 'missing-brief', 'invalid-metadata',
    'installed-without-targets', 'noncontiguous',
])
def test_prerequisite_repair_refuses_unsafe_queue_mutations(tmp_path, defect):
    plan, state = prerequisite_plan(tmp_path)
    queue = tmp_path / plan.queue
    text = queue.read_text()
    if defect == 'unknown':
        text = text.replace('| pre-a | prerequisite B', '| unknown | prerequisite B')
    elif defect == 'skipped':
        text = text.replace('| pre-a | prerequisite B', '| 001 | prerequisite B')
    elif defect == 'reordered':
        lines = text.splitlines()
        first = next(i for i, line in enumerate(lines) if line.startswith('| [x] | 001 |'))
        last = next(i for i, line in enumerate(lines) if line.startswith('| [ ] | 003 |'))
        lines[first], lines[last] = lines[last], lines[first]
        text = '\n'.join(lines) + '\n'
    elif defect == 'changed-status':
        text = text.replace('| [ ] | 003 |', '| [x] | 003 |')
    elif defect in ('consumer-scope', 'other-scope'):
        identity = '002' if defect == 'consumer-scope' else '003'
        text = text.replace(f'finite scope {identity}', 'changed obligation')
    elif defect == 'extra-unrelated':
        (tmp_path / 'docs/pre-c.md').write_text('Acceptance: host\n')
        text = text.replace('| [ ] | 002 |',
                            '| [ ] | pre-c | [Unrelated](pre-c.md) | 001 | unrelated |\n| [ ] | 002 |')
    elif defect == 'checked-new':
        text = text.replace('| [ ] | pre-a |', '| [x] | pre-a |')
        (tmp_path / plan.path).write_text('Task queue: [Queue](queue.md).\nNext task: **pre-b — Next**.\n')
    elif defect == 'missing-brief':
        (tmp_path / 'docs/pre-b.md').unlink()
    elif defect == 'invalid-metadata':
        (tmp_path / 'docs/pre-b.md').write_text('Acceptance: imaginary\n')
    elif defect == 'installed-without-targets':
        (tmp_path / 'docs/pre-b.md').write_text('Acceptance: installed\n')
    elif defect == 'noncontiguous':
        rows = text.splitlines()
        first = next(i for i, row in enumerate(rows) if row.startswith('| [ ] | pre-a |'))
        prior = next(i for i, row in enumerate(rows) if row.startswith('| [x] | 001 |'))
        rows[first], rows[prior] = rows[prior], rows[first]
        text = '\n'.join(rows) + '\n'
    queue.write_text(text)
    try:
        selected = plan.prerequisite_repair(state)
    except ValueError:
        return  # Strict parser refusals are an equally safe non-adoption outcome.
    assert selected is None


@pytest.mark.parametrize('changes', [
    {'pending_completion': {'status': 'task_complete'}},
    {'commit_intent': {}}, {'phase': 'complete'}, {'status': 'task_complete'},
    {'queue_structure': None},
])
def test_prerequisite_repair_refuses_accepted_or_unverifiable_checkpoint(tmp_path, changes):
    plan, state = prerequisite_plan(tmp_path)
    state.update(changes)
    assert plan.prerequisite_repair(state) is None


def test_prerequisite_repair_requires_added_work(tmp_path):
    plan = prepare(tmp_path)
    assert plan.prerequisite_repair(state_for(plan)) is None


def test_prerequisite_insertion_cannot_drop_existing_consumer_dependency(tmp_path):
    plan, state = prerequisite_plan(tmp_path)
    selected = next(row for row in state['queue_structure'] if row[2] == '002')
    selected[4] = '001'
    queue = tmp_path / plan.queue
    queue.write_text(queue.read_text().replace('| pre-b, 001 |', '| pre-b |'))
    assert plan.prerequisite_repair(state) is None


@pytest.mark.parametrize('declaration', ['Acceptance: review\n', 'Acceptance: host\nTargets: newly-required-target\n'])
def test_restart_refuses_changed_acceptance_metadata(rig, monkeypatch, declaration):
    previous = rig.root / 'previous'
    previous.mkdir()
    workflow.launcher.atomic(previous / 'checkpoint.json', state_for(rig.plan, in_flight=True))
    (rig.root / 'docs/001.md').write_text(declaration)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    with pytest.raises(ValueError, match='acceptance or targets changed'):
        workflow.initial_state(rig.plan, rig.spec, rig.root)


def test_task_limit_retains_last_accepted_summary_and_handoff(rig):
    assert rig.worker() == 0
    checkpoint = json.loads((rig.run / 'checkpoint.json').read_text())
    assert checkpoint['task_id'] == '001' and checkpoint['phase'] == 'complete'
    assert checkpoint['summary'] == 'Verified finite task.'
    assert checkpoint['handoff'] == 'Continue from the retained checkpoint.'
    handoff = (rig.run / 'handoff.txt').read_text()
    assert 'Continue from the retained checkpoint.' in handoff
    assert 'task limit reached' in handoff


def test_prerequisite_suspension_resumes_original_consumer_across_task_limited_runs(rig, monkeypatch):
    consumer_handoff = 'Consumer dependency discovered; preserve its partial implementation.'
    original_baseline = {'preexisting.txt': 'original private work'}
    (rig.root / 'preexisting.txt').write_text('original private work')
    monkeypatch.setattr(workflow, 'worktree_snapshot', lambda _: original_baseline.copy())
    calls = []
    def execute(root, spec, run, owner):
        state = json.loads((run / 'checkpoint.json').read_text())
        calls.append((state['task_id'], state['task_sessions']))
        assert state['stage_baseline'] == original_baseline
        if state['task_id'] == '001' and state['task_sessions'] == 1:
            queue = root / rig.plan.queue
            text = queue.read_text().replace('| [ ] | 001 |',
                '| [ ] | pre | [Required preparation](pre.md) | Baseline | finite prerequisite |\n| [ ] | 001 |')
            queue.write_text(text.replace('| — | finite scope 001', '| pre | finite scope 001'))
            (root / 'docs/pre.md').write_text('Acceptance: host\n')
            (root / rig.plan.path).write_text('Task queue: [Queue](queue.md).\nNext task: **pre — Preparation**.\n')
            result = response(state, 'prerequisite_required')
            result.update(handoff=consumer_handoff, checks=[], stage_paths=[])
            return result
        if state['task_id'] == 'pre':
            assert TaskBudget(run).read()['completed'] == 0
            saved = state['suspended_tasks']['001']
            assert saved['task_sessions'] == 1 and saved['handoff'] == consumer_handoff
            assert rig.plan.state()['001'] is False
        else:
            assert state['task_id'] == '001' and state['task_sessions'] == 2
            assert state['handoff'] == consumer_handoff
            assert 'pre' in state['queue_before'] and state['queue_before']['pre'] is True
        complete(rig.plan, state['task_id'])
        return response(state)
    monkeypatch.setattr(workflow, 'execute', execute)
    assert rig.worker() == 0
    first = json.loads((rig.run / 'checkpoint.json').read_text())
    assert first['task_id'] == 'pre' and first['phase'] == 'complete'
    assert first['suspended_tasks']['001']['task_sessions'] == 1
    assert TaskBudget(rig.run).read()['completed'] == 1
    assert rig.plan.next_task().id == '001'
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    resumed = workflow.initial_state(rig.plan, rig.spec, rig.root)
    assert resumed['suspended_tasks']['001']['session_limit'] == 6
    second_run = rig.root / 'second-run'
    second_run.mkdir()
    TaskBudget(second_run).initialize(1)
    owner = os.open(second_run / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
    assert workflow.worker(rig.root, second_run, owner, rig.spec, resumed) == 0
    assert calls == [('001', 1), ('pre', 1), ('001', 2)]
    final = json.loads((second_run / 'checkpoint.json').read_text())
    assert final['task_id'] == '001' and final['task_sessions'] == 2
    assert final['phase'] == 'complete' and not final.get('suspended_tasks')
    assert TaskBudget(second_run).read()['completed'] == 1
    assert rig.plan.next_task().id == '002'


def test_completed_prerequisite_restart_refuses_external_suspended_consumer_completion(tmp_path, monkeypatch):
    plan, consumer = prerequisite_plan(tmp_path)
    saved = state_for(plan, phase='complete', suspended_tasks={'002': consumer})
    complete(plan, 'pre-a')
    # Keep the consumer's brief so metadata validation alone cannot detect this
    # unaccepted completion introduced after the prerequisite's checkpoint.
    complete(plan, '002')
    assert (tmp_path / 'docs/002.md').exists()
    previous = tmp_path / 'previous'
    previous.mkdir()
    workflow.launcher.atomic(previous / 'checkpoint.json', saved)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    with pytest.raises(ValueError):
        workflow.initial_state(plan, workflow.PlanWorkflow('fixture-plan', plan.path), tmp_path)


def test_queue_exhaustion_refuses_orphaned_unaccepted_suspended_consumer(rig):
    consumer = state_for(rig.plan, handoff='Consumer acceptance still remains.')
    complete(rig.plan, '001')
    complete(rig.plan, '002')
    saved = dict(phase='complete', task_sessions=0, total_sessions=1,
                 suspended_tasks={'001': consumer}, handoff='Recover the unfinished consumer.')
    assert rig.worker(saved) == 1
    assert rig.calls == []
    assert json.loads((rig.run / 'result.json').read_text()) == dict(status=1, tasks=0)
    retained = json.loads((rig.run / 'checkpoint.json').read_text())
    assert retained['suspended_tasks']['001']['handoff'] == 'Consumer acceptance still remains.'


@pytest.mark.parametrize('external_completion', [None, 'pre-a', '002'])
def test_stop_immediately_after_deferral_retains_exact_unaccepted_queue(rig, monkeypatch, external_completion):
    plan, consumer = prerequisite_plan(rig.root)
    deferred = workflow.defer_to_prerequisite(plan, consumer)
    assert deferred['task_id'] is None
    assert deferred['queue_before'] == plan.state()
    (rig.run / 'stop').touch()
    assert rig.worker(deferred) == 0
    assert rig.calls == []
    assert TaskBudget(rig.run).read()['completed'] == 0
    retained = json.loads((rig.run / 'checkpoint.json').read_text())
    assert retained['task_id'] is None and retained['phase'] == 'complete'
    assert retained['suspended_tasks']['002']['task_id'] == '002'
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: rig.run)
    if external_completion is None:
        restored = workflow.initial_state(plan, rig.spec, rig.root)
        assert restored['suspended_tasks']['002']['handoff'] == consumer['handoff']
        assert restored['queue_before'] == plan.state()
    else:
        complete(plan, external_completion)
        with pytest.raises(ValueError):
            workflow.initial_state(plan, rig.spec, rig.root)
