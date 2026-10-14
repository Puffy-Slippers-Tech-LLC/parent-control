"""Composable execution-plan driver.

PlanWorkflow supplies model, acceptance and close-out policy. Markdown selection,
checkpoint recovery, task budgets, sessions, supervision and presentation stay
shared. E2E and repair keep their specialized state machines on these primitives.
"""

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detached_launcher as launcher
from execution_plan import Plan, Task, local_file, local_path, plan_namespace
from launcher_git import finish_commit, git_output, stage_task, worktree_snapshot
from launcher_progress import publish_progress
from launcher_question import BLOCKER_INSTRUCTIONS, validate_blocker, wait_for_answer
from launcher_runtime import TaskBudget, add_options, task_limit, warn_remaining


@dataclass(frozen=True)
class PlanWorkflow:
    name: str
    plan: str | None = None
    model: str = 'gpt-6.1-sol'
    effort: str = 'high'
    commit_prefix: str | None = None
    push: bool = False
    vm: bool = False
    max_sessions: int = 5


def task_record(task):
    return dict(task_id=task.id, title=task.title, brief=str(task.brief),
                **task.acceptance_metadata())


def validate_result(plan, state, result):
    fields = {'status', 'task_id', 'summary', 'handoff', 'checks', 'cleanup_complete', 'stage_paths', 'blocker'}
    if (not isinstance(result, dict) or set(result) != fields
            or result['task_id'] != state['task_id']
            or result['status'] not in ('task_complete', 'continue', 'blocked', 'prerequisite_required')
            or any(not isinstance(result[key], str) or not result[key].strip() for key in ('summary', 'handoff'))
            or type(result['cleanup_complete']) is not bool
            or not isinstance(result['stage_paths'], list)
            or any(not isinstance(path, str) for path in result['stage_paths'])
            or not isinstance(result['checks'], list)):
        raise ValueError('invalid plan session result; retain checkpoint for recovery')
    for check in result['checks']:
        if (not isinstance(check, dict) or set(check) != {'kind', 'target', 'result', 'evidence'}
                or check['kind'] not in ('installed', 'review', 'host', 'reconciliation')
                or check['result'] not in ('passed', 'failed', 'not_run')
                or any(not isinstance(check[key], str) for key in ('target', 'evidence'))):
            raise ValueError('invalid acceptance check')
    validate_task_metadata(plan, state)
    complete = result['status'] == 'task_complete'
    if result['status'] == 'blocked':
        validate_blocker(result['blocker'])
    elif result['blocker'] is not None:
        raise ValueError('only a blocked result may carry a developer question')
    if result['status'] == 'prerequisite_required':
        if not result['cleanup_complete'] or plan.prerequisite_repair(state) is None:
            raise ValueError('prerequisite handoff needs a valid backward dependency insertion and owned cleanup')
        return
    if complete:
        required = state['task']['acceptance']
        targets = state['task']['targets'] or ['']
        if (not result['cleanup_complete'] or not result['checks']
                or any(check['result'] != 'passed' or not check['evidence'].strip() for check in result['checks'])
                or any(not any(check['kind'] == required and check['target'] == target
                               for check in result['checks']) for target in targets)):
            raise ValueError('completion requires passing scoped acceptance evidence and owned cleanup')
        if not {plan.path, plan.queue}.issubset(result['stage_paths']):
            raise ValueError('completion must include master plan and queue close-out paths')
    plan.validate_transition(state['queue_before'], state['task_id'], complete=complete,
                             structure=state.get('queue_structure'))


def session_command(root, spec, run=None):
    command = launcher.agent_command(root, spec.model, spec.effort, run,
        schema=Path(__file__).with_name('plan_response.schema.json'), delegation=True)
    command[-1:-1] = ['-c', 'service_tier="default"', '-c', 'features.fast_mode=false']
    if run is not None:
        command[-1:-1] = ['-c', 'shell_environment_policy.set.ONPC_WORKFLOW_DIRECTORY=' + json.dumps(str(run))]
    # Preserve canonical queue bindings across fresh Codex command environments.
    from vm_selection import VARIABLE, BATCH
    for name in (VARIABLE, BATCH):
        if name in os.environ:
            command[-1:-1] = ['-c', f'shell_environment_policy.set.{name}=' + json.dumps(os.environ[name])]
    return command


def session_prompt(plan, spec, state):
    return f"""Implement only task {state['task_id']}: {state['task']['title']}.
Read AGENTS.md, docs/Execution-Plans.md, {plan.path}, and the selected brief
{state['task']['brief']}; follow only applicable owning contracts and source.
Your coordinator model is {spec.model} {spec.effort}. Keep this model/effort;
there is no automatic escalation. Use GPT-6.1 Sol subagents of appropriate
effort as needed; routine read-only monitoring uses plan_monitor (Low), routine
coverage refreshes and bounded implementation use plan_worker (Medium).
Give each subagent explicit scope and disjoint write ownership. Join and close
all subagents before acceptance, handoff or cleanup. You own the final decision.
Preserve pre-existing work; do not stage, commit, push or run another workflow
launcher. The controller owns Git close-out after validated task completion.
Finish the task's actual acceptance ({state['task']['acceptance']}) on all named
targets {state['task']['targets']}, and owned cleanup. Use maintained public
routes; an evidence summary, source review or host test cannot substitute for
required installed acceptance. Verify exact input/evidence applicability.
Only after acceptance, check this queue row, advance the master Next task pointer
to the first unchecked row (Next task: none. when finished), record concise
evidence in the queue/reference and remove its temporary brief if appropriate.
Preserve every other row's status, order and scope. If this session cannot finish,
leave this task unchecked and the pointer on it; return continue with a usable
handoff. For a newly discovered prerequisite, insert only explicit unchecked
prerequisite rows immediately before this unfinished consumer, with valid briefs
and backward Requires links, and move Next task to the first new prerequisite.
Preserve all existing rows' completion, relative order and scope. After owned
cleanup return prerequisite_required; this suspends the consumer without any
acceptance credit and resumes it after its declared prerequisites pass. Do not
use this route to drop obligations, skip blockers or reorder existing work.
An interrupted predecessor may have checked its row before saving an accepted
result. Reconcile its retained evidence and cleanup, complete missing work or
restore its unchecked row/brief/pointer before returning continue or blocked.
{BLOCKER_INSTRUCTIONS}
Send LAUNCHER_STATUS {{"explanation":"Plain-language purpose of this task"}}
in your first commentary, and LAUNCHER_STATUS {{"status":"Current result or issue"}}
when useful. These are presentation only. Return the required JSON response.
Each checks item names kind, one declared canonical target (empty only when the
brief declares no Targets), actual
passed/failed/not_run result and exact retained evidence or review findings.
Never report task_complete unless every required check passed and cleanup ended.
Previous handoff/recovery: {state.get('handoff', 'No prior session.')}
Developer answer: {json.dumps(state.get('answer'))}
"""


def validate_task_metadata(plan, state):
    """A fresh session must not silently reuse weaker saved acceptance targets."""
    brief = Path(state['task']['brief'])
    if not brief.exists() and (state.get('in_flight') or state.get('pending_completion')):
        return  # Recovery may restore a brief removed during partial close-out.
    brief = local_file(plan.root, str(brief.relative_to(plan.root)))
    current = task_record(Task(state['task_id'], False, state['title'], brief, ()))
    if any(current[key] != state['task'][key] for key in ('acceptance', 'targets')):
        raise ValueError('task acceptance or targets changed since its checkpoint; reconcile the retained handoff')


def defer_to_prerequisite(plan, state):
    task = plan.prerequisite_repair(state)
    if task is None:
        raise ValueError('queue repair is not a valid prerequisite insertion')
    pending = dict(state.get('suspended_tasks', {}))
    consumer = {key: value for key, value in state.items() if key != 'suspended_tasks'}
    consumer.update(phase='recover', in_flight=False)
    pending[state['task_id']] = consumer
    return dict(phase='complete', suspended_tasks=pending, total_sessions=state.get('total_sessions', 0),
                task_sessions=0, replan_baseline=state['stage_baseline'],
                protected_staged=state['protected_staged'],
                task_id=None, queue_before=plan.state(), queue_structure=plan.structure(),
                handoff=f"Implement prerequisite {task.id} before resuming unfinished task {state['task_id']}. "
                        + state.get('handoff', ''))


def initial_state(plan, spec, directory):
    previous = launcher.current_run(directory)
    if previous and (previous / 'checkpoint.json').exists():
        state = json.loads((previous / 'checkpoint.json').read_text())
        for saved in [state, *state.get('suspended_tasks', {}).values()]:
            if saved.get('task') and saved.get('phase') != 'complete':
                validate_task_metadata(plan, saved)
                saved['session_limit'] = saved.get('task_sessions', 0) + spec.max_sessions
        if state.get('phase') != 'complete':
            try:
                plan.validate_recovery(state)
            except ValueError:
                if plan.prerequisite_repair(state) is None:
                    raise
                state = defer_to_prerequisite(plan, state)
            state['recovery_run'] = str(previous)
            question_path = previous / 'question.json'
            if state.get('phase') == 'blocked' and question_path.exists():
                question = json.loads(question_path.read_text())
                if question['id'] == state.get('blocker_id') and question.get('answer') is not None:
                    state.update(phase='recover', answer={'question': question['question'], 'answer': question['answer']})
            return state
        if state.get('suspended_tasks'):
            plan.validate_recovery(state)
            state['recovery_run'] = str(previous)
            return state
    return {'phase': 'complete', 'task_sessions': 0, 'total_sessions': 0}


def closeout(plan, spec, run, state):
    result = state['pending_completion']
    validate_result(plan, state, result)
    if spec.commit_prefix:
        paths = state.get('commit_intent', {}).get('paths')
        if paths is None:
            paths = list(dict.fromkeys(result['stage_paths']))
            overlap = set(paths) & (set(state['stage_baseline']) | set(state['protected_staged']))
            if overlap:
                raise ValueError('close-out overlaps pre-existing work: ' + ', '.join(sorted(overlap)))
            paths = stage_task(plan.root, paths, required_paths=(plan.path, plan.queue))
        finish_commit(plan.root, run, state, paths, f"{spec.commit_prefix}: Completed task {state['task_id']}")
        if spec.push:
            pushed = git_output(plan.root, 'push', check=False)
            if pushed.returncode:
                raise ValueError('completion push failed: ' + pushed.stderr.strip())
    state.update(phase='complete', in_flight=False, summary=result['summary'], handoff=result['handoff'])
    state.pop('pending_completion', None)
    state.pop('commit_intent', None)
    launcher.atomic(run / 'checkpoint.json', state)


def execute(root, spec, run, owner):
    command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), '--supervise',
               str(root), str(run), str(owner), json.dumps(asdict(spec))]
    with subprocess.Popen(command, cwd=root, env=launcher.environment(), stdin=subprocess.PIPE,
                          pass_fds=(owner, *launcher.scratch_descriptors()), start_new_session=True) as child:
        status = child.wait()
    sys.stdout.flush()
    launcher.compact_log(run / 'output', writer_fd=1)
    if (run / 'cancel').exists():
        raise launcher.Stopped()
    if status:
        raise ValueError(f'agent session exited {status}; inspect retained output and handoff')
    return json.loads((run / 'agent-result.json').read_text())


def worker(root, run, owner, spec, state):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: (run / 'cancel').touch(mode=0o600))
    plan = Plan.load(root, spec.plan)
    budget = TaskBudget(run)
    status, reason = 0, 'queue complete'
    try:
        if state.get('recovery_run'):
            launcher.finish_nested(root, Path(state['recovery_run']))
        if state.get('pending_completion'):
            closeout(plan, spec, run, state)
            budget.complete()
            print(f"{spec.name}: recovered task {state['task_id']} close-out.", flush=True)
        while True:
            if (run / 'cancel').exists():
                raise launcher.Stopped()
            if (run / 'stop').exists():
                reason = 'stopped at a session boundary'
                break
            admitted = False
            if state['phase'] == 'complete':
                if state.get('queue_before'):
                    plan.validate_recovery(state)
                task = plan.next_task()
                if task is None:
                    if state.get('suspended_tasks'):
                        raise ValueError('queue exhausted with unaccepted suspended tasks; reconcile the retained handoff')
                    reason = 'queue complete'
                    break
                if not budget.admit():
                    reason = 'task limit reached'
                    break
                admitted = True
                pending = dict(state.get('suspended_tasks', {}))
                inherited_baseline = state.get('replan_baseline')
                inherited_staged = state.get('protected_staged')
                if task.id in pending:
                    selected = dict(pending.pop(task.id))
                    validate_task_metadata(plan, selected)
                    selected.update(total_sessions=state.get('total_sessions', 0),
                                    queue_before=plan.state(), queue_structure=plan.structure(selected=task.id))
                else:
                    selected = dict(task_record(task), task=task_record(task), phase='implement',
                             task_sessions=0, total_sessions=state.get('total_sessions', 0),
                             session_limit=spec.max_sessions,
                             stage_baseline=inherited_baseline if inherited_baseline is not None else worktree_snapshot(root),
                             protected_staged=inherited_staged if inherited_baseline is not None else
                                list(filter(None, git_output(root, 'diff', '--cached', '--name-only', '-z').stdout.split('\0'))),
                             queue_before=plan.state(), queue_structure=plan.structure(selected=task.id))
                if pending:
                    selected.update(suspended_tasks=pending, replan_baseline=selected['stage_baseline'])
                state = selected
            if state['phase'] == 'blocked':
                launcher.atomic(run / 'chat-state.json', {'session': state.get('total_sessions'),
                    'task_id': state['task_id'], 'task_session': state['task_sessions'], 'status': 'blocked'})
                answer = wait_for_answer(run, state['blocker'], state['blocker_id'],
                    state['task_id'], label=spec.name, heading=f"Task {state['task_id']}: {state['title']}")
                if answer is None:
                    reason = 'stopped at a session boundary'
                    break
                state['answer'] = answer
                state['phase'] = 'recover'
                state['session_limit'] = max(state['session_limit'], state['task_sessions'] + 1)
            if not admitted and not budget.admit():
                reason = 'task limit reached'
                break
            if state['task_sessions'] >= state['session_limit']:
                status, reason = 1, 'task session limit reached; resume with a fresh run'
                break
            state['task_sessions'] += 1
            state['total_sessions'] += 1
            state['in_flight'] = True
            remaining = sum(not done for done in state['queue_before'].values())
            budget.update(lambda value: value.update(remaining=remaining + value['completed']))
            launcher.atomic(run / 'checkpoint.json', state)
            (run / 'prompt.txt').write_text(session_prompt(plan, spec, state))
            (run / 'agent-result.json').unlink(missing_ok=True)
            launcher.atomic(run / 'nested.json', [])
            (run / 'nested-closed').unlink(missing_ok=True)
            publish_progress(run, state['task_id'], [f"Task {state['task_id']}: {state['title']}",
                f"Session [{state['task_sessions']}]: {spec.model} {spec.effort}"])
            result = execute(root, spec, run, owner)
            validate_result(plan, state, result)
            state.update(summary=result['summary'], handoff=result['handoff'], in_flight=False)
            if result['status'] == 'task_complete':
                state['pending_completion'] = result
                launcher.atomic(run / 'checkpoint.json', state)
                closeout(plan, spec, run, state)
                budget.complete()
                publish_progress(run, 'complete-' + state['task_id'],
                    [f"Task {state['task_id']}: {state['title']} — complete"], replaces=[state['task_id']])
            elif result['status'] == 'blocked':
                state.update(phase='blocked', blocker=result['blocker'], blocker_id=uuid.uuid4().hex)
            elif result['status'] == 'prerequisite_required':
                consumer, title = state['task_id'], state['title']
                state = defer_to_prerequisite(plan, state)
                publish_progress(run, consumer, [f'Task {consumer}: {title} — suspended for prerequisite'])
            else:
                state['phase'] = 'recover'
            launcher.atomic(run / 'checkpoint.json', state)
    except launcher.Stopped:
        status, reason = 130, 'cancelled after owned cleanup'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        status, reason = 1, str(error)
    finally:
        try:
            launcher.finish_nested(root, run)
            state['reason'] = reason
            launcher.atomic(run / 'checkpoint.json', state)
            (run / 'handoff.txt').write_text(state.get('handoff', '') + '\n' + reason + '\n')
            budget.close()
            print(f'{spec.name}: {reason}.', flush=True)
            launcher.atomic(run / 'result.json', {'status': status, 'tasks': budget.read()['completed']})
        finally:
            os.close(owner)
    return status


def main(spec=PlanWorkflow('execute-plan'), argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description='Run or resume an ordered execution plan.', allow_abbrev=False)
    parser.add_argument('--plan', default=spec.plan, required=spec.plan is None,
                        help='checkout-relative master Markdown plan')
    parser.add_argument('--vm', help='registered selector; omitted: configured enabled queue for VM workflows')
    parser.add_argument('--check', action='store_true', help='validate plan, queue and unfinished briefs without execution')
    add_options(parser)
    args = parser.parse_args(argv)
    run = None
    interrupted = False

    def cancel(*_):
        nonlocal interrupted
        interrupted = True
        if run is not None:
            (run / 'cancel').touch(mode=0o600)

    previous_signal = signal.signal(signal.SIGINT, cancel)
    try:
        # Ownership depends on the master's stable path, not on editable plan
        # contents. Attach and stop must work during interrupted plan edits.
        master = local_path(root, args.plan)
        path = str(master.relative_to(root.resolve()))
        spec = PlanWorkflow(**dict(asdict(spec), plan=path))
        if args.check:
            plan = Plan.load(root, path)
            records = [task_record(task) for task in plan.tasks() if not task.complete]
            print(json.dumps({'plan': plan.path, 'queue': plan.queue,
                              'next_task': records[0]['task_id'] if records else None,
                              'remaining': len(records), 'model': spec.model, 'effort': spec.effort}))
            return 0
        from vm_selection import execution_selection, execution_binding, check_binding, save_binding, VARIABLE, BATCH
        if not args.stop and (spec.vm or args.vm):
            execution_selection(args.vm)
        else:
            os.environ.pop(VARIABLE, None)
            os.environ.pop(BATCH, None)
        binding = execution_binding()
        initial = {}
        initial_remaining = 0
        def attach(selected):
            check_binding(selected, binding, stopping=args.stop)
            if args.tasks is not None:
                budget = TaskBudget(selected)
                limit = budget.set_limit(args.tasks)
                try:
                    remaining = sum(not task.complete for task in Plan.load(root, path).tasks())
                except (OSError, ValueError):
                    pass  # Editable metadata must never prevent attachment.
                else:
                    warn_remaining(limit, remaining + budget.read()['completed'], label=spec.name)
                print(f"{spec.name}: limits now tasks={limit if limit is not None else 'all'}", flush=True)
        def command(selected, owner):
            nonlocal initial_remaining
            plan = Plan.load(root, path)
            validation_error = None
            try:
                records = [task_record(task) for task in plan.tasks() if not task.complete]
            except ValueError as error:
                validation_error = error
                records = []
            initial.update(initial_state(plan, spec, selected.parent))
            if records or initial.get('phase') != 'complete':
                session_command(root, spec)  # Dependency/transport preflight, no model session.
            if validation_error is not None:
                if not initial.get('in_flight') and not initial.get('pending_completion'):
                    raise validation_error
                remaining = sum(not done for done in initial['queue_before'].values())
                initial['handoff'] = (initial.get('handoff', '') + '\nReconcile interrupted close-out: ' + str(validation_error))
            else:
                remaining = len(records)
            initial_remaining = remaining
            warn_remaining(task_limit(args.tasks if args.tasks is not None else 1), remaining, label=spec.name)
            return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), '--worker',
                    str(root), str(selected), str(owner), json.dumps(asdict(spec)), json.dumps(initial)]
        def start(selected):
            TaskBudget(selected).initialize(args.tasks if args.tasks is not None else 1,
                                            remaining=initial_remaining)
            launcher.atomic(selected / 'checkpoint.json', initial)
            save_binding(selected, binding)
        run, started = launcher.select(root, 'plans', command, stop=args.stop, stop_marker='stop',
                                       on_attach=attach, on_start=start, namespace=plan_namespace(path))
        if run is None:
            print(f'{spec.name}: no active launcher.')
            return 0
        if interrupted:
            cancel()
        print(f"{spec.name}: {'started' if started else 'attached to'} {run.name}; log: {run / 'output'}", flush=True)
        print('Closing the terminal detaches. --stop waits for a session boundary. Chat Ctrl+C interrupts; again while waiting exits.', flush=True)
        from launcher_view import WorkflowView, plan_progress, plan_totals
        return launcher.follow(run, label=spec.name, view=WorkflowView(
            'chat', True, plan_progress, lambda: plan_totals(root, path)))
    except BrokenPipeError:
        return 0
    except (OSError, ValueError, KeyError, ImportError, subprocess.SubprocessError) as error:
        print(f'{spec.name}: {error}', file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGINT, previous_signal)


if __name__ == '__main__':
    mode, root, run, owner, spec, *options = sys.argv[1:]
    root, run, owner, spec = Path(root), Path(run), int(owner), PlanWorkflow(**json.loads(spec))
    if mode == '--worker':
        sys.exit(worker(root, run, owner, spec, json.loads(options[0])))
    if mode == '--supervise':
        sys.exit(launcher.supervise(root, run, owner, 'agent', session_command(root, spec, run),
                                   nested=True, interactive=True, hide_task_completion=True))
    raise SystemExit('private execution-plan worker entry point')
