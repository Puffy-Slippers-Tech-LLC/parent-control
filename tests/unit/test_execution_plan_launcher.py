"""Private plan fixtures exercise shared selection, recovery, budgets and panes."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from types import SimpleNamespace

import pytest

from execution_plan import Plan, local_file
from confinement_workflow import WORKFLOW as CONFINEMENT
from launcher_display import TaskDisplay
from launcher_runtime import TaskBudget, task_limit, task_progress, warn_remaining
from launcher_view import WorkflowView, plan_totals, view_for
import plan_launcher as workflow
from plan_launcher import execute as execute_session
from tests.support.terminal_screen import Terminal


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
    assert task_progress(tmp_path, steps)[0]['lines'] == [f'Tasks: 1/{total}']
    budget.complete()
    assert task_progress(tmp_path, steps)[0]['lines'] == [f'Tasks: 2/{total}']
    budget.set_limit(0)
    assert task_progress(tmp_path, steps)[0]['lines'] == ['Tasks: 2/5']
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
    assert counters == (['Tasks: 1/1'] if already_complete else ['Tasks: 1/2', 'Tasks: 2/2'])


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


def test_interrupted_partial_closeout_resumes_without_a_brief(rig, monkeypatch):
    previous = rig.root / 'previous'
    previous.mkdir()
    state = state_for(rig.plan, in_flight=True, task_sessions=2)
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
    assert rig.cleanups == [previous, rig.run]


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
        assert view.progress(run, [], [])[0]['lines'] == ['Tasks: 1/2']
        assert (run / 'limits.json').read_text() == original
        # Later task completion and explicit limits use current plan data.
        complete(rig.plan, '001')
        budget.complete()
        assert view.progress(run, [], [])[0]['lines'] == ['Tasks: 2/2']
        budget.set_limit(3)
        assert view.progress(run, [], [])[0]['lines'] == ['Tasks: 2/3']
        return 0

    monkeypatch.setattr(workflow.launcher, 'select', select)
    monkeypatch.setattr(workflow.launcher, 'follow', follow)
    assert workflow.main(rig.spec, []) == 0


def test_e2e_observer_counts_legacy_unlimited_run(tmp_path, monkeypatch):
    import launcher_view
    TaskBudget(tmp_path).initialize(0)
    monkeypatch.setattr(launcher_view, 'e2e_totals', lambda: (17, 9, 26))
    assert view_for('write-e2e').progress(tmp_path, [], [])[0]['lines'] == ['Tasks: 1/9']


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


def test_retained_completion_recovers_estimate_closeout_without_another_session(rig, monkeypatch):
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
    retained = (previous / 'checkpoint.json').read_bytes()
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    recovered = workflow.initial_state(rig.plan, rig.spec, rig.root)
    assert (previous / 'checkpoint.json').read_bytes() == retained
    assert recovered['pending_completion'] == result and not recovered['in_flight']
    assert recovered['task_sessions'] == 2 and recovered['total_sessions'] == 3
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
    assert [event[0] for event in events] == ['cleanup', 'stage', 'commit', 'push', 'cleanup']
    assert events[0][1] == previous
    assert TaskBudget(rig.run).read()['completed'] == 1
    final = json.loads((rig.run / 'checkpoint.json').read_text())
    assert final['phase'] == 'complete' and 'pending_completion' not in final
    assert rig.plan.next_task().id == '002'


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


@pytest.mark.parametrize('protected', ['stage_baseline', 'protected_staged'])
def test_closeout_refuses_preexisting_claimed_changes(rig, monkeypatch, protected):
    state = state_for(rig.plan)
    state[protected] = {'docs/plan.md': 'original'} if protected == 'stage_baseline' else ['docs/plan.md']
    state['pending_completion'] = response(state)
    complete(rig.plan, '001')
    monkeypatch.setattr(workflow, 'stage_task', lambda *_args, **_kwargs: pytest.fail('must not stage protected work'))
    with pytest.raises(ValueError, match='overlaps pre-existing work'):
        workflow.closeout(rig.plan, replace(rig.spec, commit_prefix='Fixture'), rig.run, state)


@pytest.mark.parametrize('mode', ['none', 'question'])
def test_nonchat_shared_panes_resize_and_scroll_without_composer(tmp_path, mode):
    terminal = Terminal(120, 30)
    display = TaskDisplay(terminal, run=tmp_path, input_mode=mode, terminal_size=lambda: terminal.size)
    try:
        display.task_info = dict(explanation='\n'.join(f'Purpose {n}' for n in range(60)), status='Reviewing.')
        display.update([dict(key='count', pinned=True, lines=['Tasks: 1/2']),
                        dict(key='task', lines=['Current task', 'Current session'])], [])
        display.write('Execution output\n')
        visible = terminal.visible()
        assert visible.splitlines()[0].split('│')[0].strip() == 'Tasks: 1/2'
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
    TaskBudget(run).initialize(1)
    terminal = Terminal(120, 30)
    view = WorkflowView(totals=lambda: plan_totals(tmp_path, plan.path))
    display = view.display(terminal, run)
    display.terminal_size = lambda: terminal.size
    queue = tmp_path / plan.queue
    try:
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 0/4/4' in terminal.visible()
        # Queue completion can precede pointer/brief close-out; no worker output
        # or budget update is needed to refresh the observer.
        queue.write_text(queue.read_text().replace('| [ ] | 001 |', '| [x] | 001 |'))
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 1/3/4' in terminal.visible()
        assert TaskBudget(run).read()['completed'] == 0
        row = display.previous[0]
        start = row.plain.index('Total Tasks: ') + len('Total Tasks: ')
        assert row.get_style_at_offset(display.console, start).color.name == 'green'
        assert row.get_style_at_offset(display.console, start + 2).color.name == 'blue'
        assert row.get_style_at_offset(display.console, start + 4).color is None
        valid = queue.read_text()
        queue.write_text('Partial rewrite')
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 1/3/4' in terminal.visible()
        queue.write_text(valid.replace('| [ ] | 002 |', '| [x] | 002 |'))
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
        display.refresh_chat()
        display.draw()
        assert 'Total Tasks: 5/0/5' in terminal.visible()
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


def test_confinement_model_and_bounded_sol_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow.launcher.shutil, 'which', lambda _: '/private/codex')
    command = workflow.session_command(tmp_path, CONFINEMENT, tmp_path)
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
                 'launcher_git.py', 'launcher_progress.py', 'launcher_question.py',
                 'launcher_runtime.py', 'test_storage.py']:
        shutil.copy2(source / name, tools / name)
    result = subprocess.run([sys.executable, '-B', str(tools / 'execute-plan'), '--plan', 'docs/plan.md', '--check'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == dict(plan='docs/plan.md', queue='docs/queue.md',
                                           next_task='001', remaining=2, model='gpt-6.1-sol', effort='high')
    assert not (tmp_path / 'output').exists()


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
        'execute-plan', 'plan_launcher.py', 'execution_plan.py', 'detached_launcher.py',
        'launcher_git.py', 'launcher_runtime.py', 'launcher_progress.py',
        'launcher_question.py', 'launcher_view.py', 'launcher_display.py',
        'launcher_chat.py', 'launcher_render.py', 'watch_output.py', 'vm_selection.py',
        'test_storage.py', 'test_retention.py', 'test_input_transfer.py',
        'plan_response.schema.json', 'plan_monitor.toml', 'plan_worker.toml',
    ]
    for name in names:
        shutil.copy2(source / name, tools / name)
    integration = tmp_path / 'tests/integration'
    integration.mkdir(parents=True)
    shutil.copy2(source.parent / 'tests/integration/vm_config.py', integration / 'vm_config.py')
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True, timeout=10)
    (tmp_path / '.git/info/exclude').write_text('output/\nbin/\nscript.json\ncalls.jsonl\nagent-ready-*\n')
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
    assert subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=tmp_path,
                          capture_output=True, timeout=10).returncode != 0
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
    checkpoint = json.dumps(state, sort_keys=True)
    selected = plan.prerequisite_repair(state)
    assert selected.id == 'pre-a' and selected.brief == tmp_path / 'docs/pre-a.md'
    assert [task.id for task in plan.tasks()] == ['001', 'pre-a', 'pre-b', '002', '003']
    assert plan.state() == {'001': True, 'pre-a': False, 'pre-b': False, '002': False, '003': False}
    assert json.dumps(state, sort_keys=True) == checkpoint
    assert state['task_id'] == '002' and 'unfinished' in state['handoff']


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
