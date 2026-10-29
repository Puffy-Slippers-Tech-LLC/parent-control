"""Composable execution-plan driver.

PlanWorkflow supplies model, acceptance and close-out policy. Markdown selection,
checkpoint recovery, task budgets, sessions, supervision and presentation stay
shared. E2E and repair keep their specialized state machines on these primitives.
"""

import argparse
from contextlib import ExitStack
from dataclasses import asdict, dataclass, replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detached_launcher as launcher
from execution_plan import Plan, Task, local_file, local_path, plan_namespace, queue_state
from launcher_git import (GitReconciliationRequired, OwnershipReconciliationRequired,
                          closeout_lock, commit_push_propagate, git_output,
                          pull_before_commit, reconciliation_instructions, stage_task,
                          validate_closeout_ownership, validate_pull_identity, worktree_snapshot)
from launcher_progress import publish_completion, publish_progress, session_lines, task_heading
from launcher_reload import ReloadRequest, ReloadRequested, replace as replace_interpreter
from launcher_question import BLOCKER_INSTRUCTIONS, validate_blocker, wait_for_answer
from launcher_runtime import (AgentCapacityUnavailable, CAPACITY_RETRY_DELAYS, SessionResultRejected, TaskBudget,
                              add_options, capacity_failure, capacity_retry,
                              capacity_session_recovery, read_session_result,
                              retain_result_rejection, result_recovery_instructions, result_rejection, task_limit,
                              validate_session_result, warn_remaining)


@dataclass(frozen=True)
class PlanWorkflow:
    name: str
    plan: str | None = None
    model: str = 'gpt-6.1-sol'
    effort: str = 'high'
    commit_prefix: str | None = 'TA'
    vm: bool = False
    max_sessions: int = 5


MAX_REPAIR_SESSIONS = 3


def task_session_usage(state):
    """Keep the existing turn identities while charging task work separately."""
    repairs = state.get('repair_sessions', 0)
    if type(repairs) is not int or not 0 <= repairs <= state['task_sessions']:
        raise ValueError('invalid retained coordinator repair session count')
    return state['task_sessions'] - repairs


def coordinator_repair(state):
    return any(state.get(key) for key in ('git_reconciliation', 'result_recovery'))


def capacity_session_spec(spec, state):
    """A capacity fallback never mutates the workflow's configured model/effort."""
    recovery = state.get('capacity_recovery', {})
    if (capacity_retry(state) and recovery.get('failures') == len(CAPACITY_RETRY_DELAYS) + 1
            and spec.model == 'gpt-6.1-sol'):
        return replace(spec, model='gpt-6-astra')
    return spec


def task_record(task):
    return dict(task_id=task.id, title=task.title, brief=str(task.brief),
                **task.acceptance_metadata())


def validate_result_payload(state, result):
    """Use the same result shape and acceptance gates for close-out and recovery."""
    fields = {'status', 'task_id', 'summary', 'handoff', 'checks', 'cleanup_complete', 'stage_paths', 'blocker'}
    if (not isinstance(result, dict) or not fields.issubset(result)
            or result['task_id'] != state['task_id']
            or result['status'] not in ('task_complete', 'continue', 'blocked', 'prerequisite_required')
            or any(not isinstance(result[key], str) or not result[key].strip() for key in ('summary', 'handoff'))
            or type(result['cleanup_complete']) is not bool
            or not isinstance(result['stage_paths'], list)
            or any(not isinstance(path, str) for path in result['stage_paths'])
            or not isinstance(result['checks'], list)):
        raise ValueError('invalid plan session result; retain checkpoint for recovery')
    for check in result['checks']:
        if (not isinstance(check, dict) or not {'kind', 'target', 'result'}.issubset(check)
                or check['kind'] not in ('installed', 'review', 'host', 'reconciliation')
                or check['result'] not in ('passed', 'failed', 'not_run')
                or not isinstance(check['target'], str)
                or 'evidence' in check and not isinstance(check['evidence'], str)):
            raise ValueError('invalid acceptance check')
    if result['status'] == 'blocked':
        validate_blocker(result['blocker'])
    elif result['blocker'] is not None:
        raise ValueError('only a blocked result may carry a developer question')
    if result['status'] == 'task_complete':
        required = state['task']['acceptance']
        targets = state['task']['targets'] or ['']
        if (not result['cleanup_complete'] or not result['checks']
                or any(check['result'] != 'passed' for check in result['checks'])
                or any(not any(check['kind'] == required and check['target'] == target
                               for check in result['checks']) for target in targets)):
            raise ValueError('completion requires passing scoped checks and owned cleanup')


def prerequisite_handoff(plan, state, result):
    """Only an explicit planned prerequisite handoff expands the selection."""
    return result['status'] == 'prerequisite_required'


def validate_result(plan, state, result):
    validate_task_metadata(plan, state)
    validate_result_payload(state, result)
    current = plan.state(selected=state.get('selected_tasks'))
    if (result['status'] == 'task_complete' and state['task_id'] in current
            and not current[state['task_id']]):
        raise ValueError('only the selected task can complete after its current queue row is checked')
    if prerequisite_handoff(plan, state, result):
        if state.get('git_reconciliation'):
            raise ValueError('Git reconciliation must finish the retained task before selecting prerequisites')
        if not result['cleanup_complete'] or plan.prerequisite_repair(state) is None:
            raise ValueError('prerequisite handoff needs a valid backward dependency insertion and owned cleanup')
        return


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
Read AGENTS.md, docs/Execution-Plans.md, master {plan.path}, ordered queue
{plan.queue}, and the selected brief
{state['task']['brief']}; follow only applicable owning contracts and source.
Apply docs/Mandates/Test-Scope-Mandate.md before adding or restoring coverage;
do not recreate excluded non-product tests for task briefs or old task histories.
Use these exact checkout-relative paths. Resolve other document links relative
to their containing document; do not infer filenames from titles or launcher names.
Your coordinator model for this session is {spec.model} {spec.effort}.
This is a {state.get('session_kind', 'task')} session. Task implementation has used
{task_session_usage(state)}/{state['session_limit']} sessions; coordinator repairs
have used {state.get('repair_sessions', 0)}/{MAX_REPAIR_SESSIONS}. Driver repairs
use only the separate repair allowance and preserve this same task's acceptance.
Capacity fallback applies only to this session and preserves reasoning effort;
the next session uses the workflow's configured model again. There is no
automatic escalation for task difficulty. By default, use GPT-6.1 Sol subagents of appropriate effort as needed;
routine read-only monitoring uses plan_monitor (Low), routine
coverage refreshes and bounded implementation use plan_worker (Medium).
For product backend code involving core functionalities, follow AGENTS.md's
model, effort, consultation and mandatory independent Astra xHigh review
requirements. These take precedence over the coordinator/subagent defaults above.
Delegate scoped implementation or review to subagents configured as required by
AGENTS.md when the coordinator or plan_worker defaults do not meet those requirements.
Use the shared backend_reviewer role for the mandatory independent backend review.
Give each subagent explicit scope and disjoint write ownership. Join and close
all subagents before completion, handoff or cleanup. You own the final decision.
Preserve pre-existing work; do not stage, commit, push or run another workflow
launcher. The controller owns Git close-out after validated task completion.
Complete the task's checks ({state['task']['acceptance']}) on its targets
{state['task']['targets']} and finish owned cleanup. You own that validation.
Use maintained public routes and check the actual requested behavior.
Then check this queue row and advance Next task to the first unchecked row
(Next task: none. when finished). A short completion note is enough; do not
create proof files, collect report bundles or repair completed tasks' report links.
Remove the temporary brief if appropriate.
Use the current queue and briefs. Parallel changes are authoritative; do not
restore removed tasks or old scope/acceptance declarations from the checkpoint.
If this session cannot finish,
leave this task unchecked and the pointer on it; return continue with a usable
handoff. At close-out, you may update this row's Estimate with a short result;
keep its Scope and Requires unchanged. For a newly discovered prerequisite,
insert only explicit unchecked prerequisite rows immediately before this unfinished consumer, with valid briefs
and backward Requires links, and move Next task to the first new prerequisite.
Add those prerequisites to this consumer's Requires chain, preserving its existing
dependencies. This is the only permitted Requires change during insertion.
Preserve all existing rows' completion, relative order and scope. After owned
cleanup return prerequisite_required; this suspends the consumer without any
acceptance credit and resumes it after its declared prerequisites pass. Do not
use this route to drop obligations, skip blockers or reorder existing work.
An interrupted predecessor may have checked its row before saving an accepted
result. Reconcile its recorded outcome and cleanup, complete missing work or
restore its unchecked row/brief/pointer before returning continue or blocked.
{BLOCKER_INSTRUCTIONS}
Return the required JSON response.
Each checks item contains only kind, one declared canonical target (empty only when the
brief declares no Targets), and the actual passed/failed/not_run result.
No evidence field or report reference is required.
Never report task_complete unless every required check passed and cleanup ended.
Previous handoff/recovery: {state.get('handoff', 'No prior session.')}
{('The preceding turn ended because the provider was at capacity. Reconcile partial '
  'work and retained command/test results after owned cleanup, then continue this '
  'same task and session. No acceptance or extra task-session allowance was granted. Failure: '
  + state['capacity_recovery']['message']) if state.get('capacity_recovery') else ''}
Developer answer: {json.dumps(state.get('answer'))}
{reconciliation_instructions(state)}
{result_recovery_instructions(state.get('result_recovery'), allowance='separate coordinator repair allowance')}
"""


def validate_consolidated_metadata(record, obligations):
    originals = obligations.get(record['task_id'], [])
    if originals and (any(item['acceptance'] != record['acceptance'] for item in originals)
            or set(record['targets']) != {target for item in originals for target in item['targets']}):
        raise ValueError('consolidated task must retain its original acceptance kind and all targets')


def validate_task_metadata(plan, state):
    """Use the current task definition without comparing it to a snapshot."""
    if (not Path(state['task']['brief']).exists() and (any(state.get(key) for key in
            ('in_flight', 'pending_completion', 'git_reconciliation', 'result_recovery'))
            or capacity_session_recovery(state))):
        return  # A finished/interrupted turn may already have removed its brief.
    task = next((task for task in plan.tasks(selected=state.get('selected_tasks'))
                 if task.id == state['task_id']), None)
    if task is not None and task.complete:
        brief = Path(state['task']['brief'])
        if not brief.exists():
            return
        task = Task(task.id, True, task.title, brief, task.requires)
    if task is not None:
        record = task_record(task)
        state.update(record, task=record)


def refresh_live_plan(plan, state):
    """Follow the surviving queue; removed tasks need no recovery or credit."""
    if state.get('git_reconciliation') or state.get('pull_intent'):
        return  # Finish the recorded Git transaction before reading conflicted metadata.
    try:
        tasks = plan.state(selected=state.get('selected_tasks', state.get('queue_before')))
        if state.get('result_recovery') and not tasks:
            # Selected-row reads permit an empty queue. A rejected partial edit
            # must not erase recovery merely because no rows remain parseable.
            queue_state(plan.root, plan.path, plan.queue, validate_pointer=False)
    except ValueError:
        if (any(state.get(key) for key in ('in_flight', 'pending_completion', 'result_recovery'))
                or capacity_session_recovery(state)):
            return  # Let the existing coordinator recover partial file edits.
        raise
    if (state.get('task_id') and state['task_id'] not in tasks
            and not state.get('commit_intent') and not state.get('pull_intent')):
        state.update(phase='complete', in_flight=False)
        for key in ('pending_completion', 'result_recovery', 'capacity_recovery'):
            state.pop(key, None)
    if state.get('suspended_tasks'):
        state['suspended_tasks'] = {key: saved for key, saved in state['suspended_tasks'].items()
                                    if key in tasks and not tasks[key]}


def defer_to_prerequisite(plan, state):
    task = plan.prerequisite_repair(state)
    if task is None:
        raise ValueError('queue repair is not a valid prerequisite insertion')
    pending = dict(state.get('suspended_tasks', {}))
    consumer = {key: value for key, value in state.items() if key != 'suspended_tasks'}
    consumer.update(phase='recover', in_flight=False)
    pending[state['task_id']] = consumer
    return dict(phase='complete', suspended_tasks=pending, total_sessions=state.get('total_sessions', 0),
                selected_tasks=list(dict.fromkeys([
                    *state.get('selected_tasks', state['queue_before']),
                    *[identity for identity in plan.state() if identity not in state['queue_before']]])),
                consolidation_obligations=state.get('consolidation_obligations', {}),
                task_sessions=0, replan_baseline=state['stage_baseline'],
                protected_staged=state['protected_staged'],
                task_id=None, queue_before=plan.state(), queue_structure=plan.structure(),
                handoff=f"Implement prerequisite {task.id} before resuming unfinished task {state['task_id']}. "
                        + state.get('handoff', ''))


def recover_rejected_completion(plan, state, previous):
    """Revalidate the exact rejected response under the fresh controller's guards."""
    recovery = state.get('result_recovery')
    if (not recovery or state.get('in_flight') or state.get('pending_completion')
            or (previous / 'agent-error.json').exists()):
        return
    response = previous / 'agent-result.json'
    retained = Path(recovery.get('response', ''))
    if retained not in (response, previous / 'rejected-agent-result.json'):
        return
    try:
        if retained != response and retained.read_bytes() != response.read_bytes():
            return  # A preceding rejection cannot authorize a different response.
        result = read_session_result(previous)
        if not isinstance(result, dict) or result.get('status') != 'task_complete':
            return
        # A completed turn may have removed its temporary brief. Apply the same
        # retained-metadata rule as interrupted completion, without changing state
        # until all acceptance, queue and cleanup guards have passed.
        candidate = dict(state, pending_completion=result, in_flight=False)
        validate_session_result(result, lambda result: validate_result(plan, candidate, result))
    except (FileNotFoundError, SessionResultRejected):
        return  # Still needs its coordinator; preserve the original rejection.
    state.pop('result_recovery')
    state.update(pending_completion=result, in_flight=False,
                 summary=result['summary'], handoff=result['handoff'])


def initial_state(plan, spec, directory, *, reloading=False):
    previous = launcher.current_run(directory)
    if previous and (previous / 'checkpoint.json').exists():
        state = json.loads((previous / 'checkpoint.json').read_text())
        refresh_live_plan(plan, state)
        # Old controllers could stop a completed task solely to archive reports.
        # Its saved successful result still owns completion; report lifetime does not.
        for saved in [state, *state.get('suspended_tasks', {}).values()]:
            renewal = saved.pop('evidence_renewal', None)
            if (renewal and not saved.get('pending_completion')
                    and renewal.get('result', {}).get('status') == 'task_complete'
                    and renewal['result'].get('task_id') == saved.get('task_id')
                    and plan.state().get(saved['task_id']) is True):
                validate_result_payload(saved, renewal['result'])
                saved.update(pending_completion=renewal['result'], in_flight=False)
            for key in ('evidence_inputs', 'evidence_source', 'evidence_turns',
                        'evidence_capture_requires_brief', 'evidence_consumers'):
                saved.pop(key, None)
        if capacity_session_recovery(state) and not reloading:
            state['capacity_recovery']['restart'] = True
        # Older workers stopped on a rejected structured handoff. Recover only
        # when the retained response reproduces that exact controller rejection;
        # process/provider failures and arbitrary interrupted edits stay guarded.
        if (state.get('in_flight') and state.get('reason') and not state.get('pending_completion')
                and (previous / 'agent-result.json').is_file()
                and not (previous / 'agent-error.json').exists()):
            try:
                result = read_session_result(previous)
                validate_session_result(result, lambda result: validate_result(plan, state, result))
            except SessionResultRejected as error:
                # Legacy JSON decoding errors lacked the shared reader's context.
                if state['reason'] in (str(error), str(error.__cause__)):
                    state.update(phase='recover', in_flight=False, plan_queue=plan.queue,
                                 result_recovery=result_rejection(error, previous / 'agent-result.json'))
        recover_rejected_completion(plan, state, previous)
        for saved in [state, *state.get('suspended_tasks', {}).values()]:
            if saved.get('task') and saved.get('phase') != 'complete':
                if not any(saved.get(key) for key in ('git_reconciliation', 'pull_intent', 'result_recovery',
                                                     'evidence_renewal')):
                    validate_task_metadata(plan, saved)
                if not reloading:
                    saved['session_limit'] = task_session_usage(saved) + spec.max_sessions
        if state.get('phase') != 'complete':
            if state.get('in_flight') and not state.get('pending_completion'):
                result_path = previous / 'agent-result.json'
                if result_path.is_file():
                    result = json.loads(result_path.read_text())
                    if isinstance(result, dict) and result.get('status') == 'task_complete':
                        # The supervisor can finish before validation/checkpointing.
                        # Reapply every acceptance and queue guard before Git writes.
                        validate_result(plan, state, result)
                        state.update(pending_completion=result, in_flight=False,
                                     summary=result['summary'], handoff=result['handoff'])
            state['recovery_run'] = str(previous)
            question_path = previous / 'question.json'
            if state.get('phase') == 'blocked' and question_path.exists():
                question = json.loads(question_path.read_text())
                if question['id'] == state.get('blocker_id') and question.get('answer') is not None:
                    state.update(phase='recover', answer={'question': question['question'], 'answer': question['answer']})
            return state
        if state.get('suspended_tasks') or state.get('consolidation_obligations'):
            state['recovery_run'] = str(previous)
            return state
        if reloading:
            return state
    return {'phase': 'complete', 'task_sessions': 0, 'total_sessions': 0}


def finished_cancellation(run, state):
    """Recognize the old worker's finished cancellation without inventing a result."""
    if (state.get('reason') != 'cancelled after owned cleanup'
            or (run / 'agent-result.json').exists() or (run / 'agent-error.json').exists()):
        return False
    for name in ('cancel', 'nested-closed', 'result.json', 'nested.json'):
        try:
            info = (run / name).lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            return False
    return (json.loads((run / 'result.json').read_text()) == dict(status=130, tasks=0)
            and json.loads((run / 'nested.json').read_text()) == [])


def reconcile_plan(root, spec, identity, *, check=False, merge_tasks=(), base=None,
                   split=None, revisions=(), propagation_head=None):
    """Explicitly adopt a committed replan, preserving the inactive checkpoint.

    This administrative operation executes no task and grants no acceptance.
    A checked row must already have been accepted and recorded in Git.
    """
    from test_storage import directory as storage_directory
    import plan_evidence_recovery  # Explicit administrative route only.
    if not isinstance(identity, str) or len(identity) != 32 or any(
            character not in '0123456789abcdef' for character in identity):
        raise ValueError('reconciliation needs the exact retained run ID')
    directory = launcher.private_directory(storage_directory('plans', root=root)
                                           / plan_namespace(spec.plan))
    with ExitStack() as locks, launcher.lock(directory / 'gate') as gate, launcher.lock(directory / 'owner') as owner:
        try:
            fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('plan reconciliation requires an inactive launcher') from None
        run = launcher.current_run(directory)
        if run is None or run.name != identity:
            raise ValueError('retained run changed; inspect the current checkpoint')
        if propagation_head is not None:
            if merge_tasks or base or split or revisions:
                raise ValueError('propagation reconciliation cannot also revise the plan')
            from launcher_worktrees import reconcile_destination, transaction_lock
            checkpoint = run / 'checkpoint.json'
            raw = plan_evidence_recovery._read(checkpoint)
            state = json.loads(raw)
            if state.get('in_flight') or not (run / 'result.json').is_file():
                raise ValueError('finish the retained session before reconciling propagation')
            with transaction_lock(root, run):
                result = reconcile_destination(root, run, state, propagation_head, check=check)
                if not check and state != json.loads(raw):
                    backup = run / ('checkpoint-before-propagation-reconcile-'
                                    + hashlib.sha256(raw).hexdigest() + '.json')
                    archived = {'checkpoint_utf8': raw.decode('utf-8')}
                    if backup.exists():
                        if json.loads(plan_evidence_recovery._read(backup)) != archived:
                            raise ValueError('propagation reconciliation backup changed')
                    else:
                        launcher.atomic(backup, archived)
                    launcher.atomic(checkpoint, state)
            return dict(run=identity, **result)
        plan = Plan.load(root, spec.plan)
        tasks = plan.tasks()
        for task in tasks:
            if not task.complete:
                task.acceptance_metadata()
        paths = [plan.path, plan.queue, *[str(task.brief.relative_to(root))
                                        for task in tasks if not task.complete]]
        # Keep pre-existing planning edits out of future task close-out conflicts.
        # Reconciliation itself never stages, commits or adopts unrelated files.
        dirty = git_output(root, '--literal-pathspecs', 'status', '--porcelain',
                           '--untracked-files=all', '--', *paths).stdout
        if dirty:
            raise ValueError('commit the reviewed plan, queue and unfinished briefs before reconciliation')
        checkpoint = run / 'checkpoint.json'
        info = checkpoint.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_size > 4 * 1024 * 1024):
            raise ValueError('unsafe retained checkpoint; preserve the run')
        raw = checkpoint.read_bytes()
        state = json.loads(raw)
        if type(state) is not dict or type(state.get('in_flight', False)) is not bool:
            raise ValueError('retained checkpoint is malformed')
        if state.get('reconciliation'):
            receipt = state['reconciliation']
            if ((merge_tasks and list(merge_tasks) != receipt.get('merge_tasks'))
                    or (base is not None and base != receipt.get('base'))
                    or (split is not None and split != receipt.get('split', {}).get('plan'))
                    or (revisions and list(revisions) != receipt.get('split', {}).get('revisions'))):
                raise ValueError('reconciliation options differ from the retained receipt')
            resumed = initial_state(plan, spec, directory)
            if resumed['phase'] != 'complete' or resumed.get('pending_completion'):
                raise ValueError('reconciled checkpoint is not ready to select its next task')
            if check:
                session_command(root, spec)  # Construct only; no model/process launch.
            return dict(run=identity, next_task=plan.next_task().id if plan.next_task() else None,
                        reconciled=True, checked=check, resume_ready=True)
        if any(state.get(key) for key in ('commit_intent', 'pull_intent', 'git_reconciliation')):
            raise ValueError('finish the retained Git transaction before reconciling the queue')
        if state.get('result_recovery'):
            if not split:
                raise ValueError('finish the retained result recovery before reconciling the queue')
            # A reviewed split may supersede a rejected structural handoff only
            # after its exact non-completion result proves completed cleanup.
            recovery = state['result_recovery']
            response = run / 'agent-result.json'
            retained = Path(recovery.get('response', ''))
            rejected_bytes = response.read_bytes()
            if (retained not in (response, run / 'rejected-agent-result.json')
                    or retained.read_bytes() != rejected_bytes
                    or (run / 'agent-error.json').exists()):
                raise ValueError('split needs the exact retained rejected result')
            rejected = json.loads(rejected_bytes)
            validate_result_payload(state, rejected)
            if rejected['status'] not in ('continue', 'prerequisite_required') or not rejected['cleanup_complete']:
                raise ValueError('split needs a non-completion handoff with owned cleanup')
        if ((state.get('in_flight') and not finished_cancellation(run, state))
                or not (run / 'result.json').is_file()):
            raise ValueError('finish the retained session before reconciling the queue')
        before, after = state['queue_before'], plan.state()
        saved_rows = state.get('queue_structure')
        if (type(before) is not dict or not before or any(type(value) is not bool for value in before.values())
                or type(saved_rows) is not list
                or any(type(row) is not list or len(row) < 6
                       or any(type(value) is not str for value in row) for row in saved_rows)
                or [row[2] for row in saved_rows] != list(before)):
            raise ValueError('retained queue is malformed; preserve the checkpoint')
        merges, transfer, obligations = {}, None, state.get('consolidation_obligations', {})
        if split:
            if merge_tasks:
                raise ValueError('split cannot be combined with task consolidation')
            from plan_reconciliation import split_plan
            target = Plan.load(root, split)
            target_directory = launcher.private_directory(storage_directory('plans', root=root) / target.namespace)
            for name in ('gate', 'owner'):
                descriptor = locks.enter_context(launcher.lock(target_directory / name))
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('split destination must be inactive and unstarted') from None
            if launcher.current_run(target_directory) is not None:
                raise ValueError('split destination must be inactive and unstarted')
            transfer = split_plan(root, plan, state, split, base, revisions, git=git_output)
        elif revisions:
            raise ValueError('scope revisions require an explicit plan split')
        elif merge_tasks or base is not None:
            from plan_reconciliation import consolidation
            merges, obligations = consolidation(root, plan, state, merge_tasks, base, git=git_output)
        elif [key for key in after if key in before] != list(before):
            raise ValueError('reconciliation cannot remove or reorder existing tasks')
        result = state.get('pending_completion')
        changed = [key for key in before if key in after and before[key] != after[key]]
        if changed:
            if (changed != [state.get('task_id')] or not after[changed[0]]
                    or result != read_session_result(run) or result.get('status') != 'task_complete'
                    or result.get('task_id') != changed[0] or result.get('cleanup_complete') is not True):
                raise ValueError('reconciliation cannot grant task completion')
            validate_result_payload(state, result)
            if not {plan.path, plan.queue}.issubset(result['stage_paths']):
                raise ValueError('retained completion lacks its plan close-out paths')
        elif result is not None:
            raise ValueError('pending completion must be recorded in the committed queue first')
        if any(after[key] for key in after if key not in before):
            raise ValueError('new plan tasks must remain unchecked')
        rows = {row[2]: row for row in plan.structure()}
        for row in (() if merges or transfer else state['queue_structure']):
            dependencies = set(row[4].split(', ')) - {'', '—', '-', 'Baseline'}
            current_dependencies = set(rows[row[2]][4].split(', ')) - {'', '—', '-', 'Baseline'}
            if row[5] != rows[row[2]][5] or not dependencies.issubset(current_dependencies):
                raise ValueError('reconciliation must preserve existing scopes and dependencies')
        if type(state.get('suspended_tasks', {})) is not dict:
            raise ValueError('retained suspended tasks are malformed')
        pending = dict(state.get('suspended_tasks', {}))
        if state.get('task') and not after[state['task_id']]:
            pending[state['task_id']] = {key: value for key, value in state.items() if key != 'suspended_tasks'}
        baseline = worktree_snapshot(root)
        staged = list(filter(None, git_output(root, 'diff', '--cached', '--name-only', '-z').stdout.split('\0')))
        for key, saved in pending.items():
            if (key not in after or after[key]):
                raise ValueError('a suspended task cannot be completed by reconciliation')
            task = next(task for task in tasks if task.id == key)
            if transfer and type(saved) is dict and saved.get('result_recovery') and key == state.get('task_id'):
                saved = dict(saved)
                saved['prior_result_recovery'] = dict(
                    metadata=saved.pop('result_recovery'),
                    response_utf8=rejected_bytes.decode('utf-8'),
                    response_sha256=hashlib.sha256(rejected_bytes).hexdigest())
            if (type(saved) is not dict or type(saved.get('task')) is not dict
                    or key != saved.get('task_id') or key != saved['task'].get('task_id')
                    or (key not in merges.values() and saved['task'].get('brief') != str(task.brief))
                    or any(saved.get(field) for field in ('pending_completion', 'commit_intent',
                        'pull_intent', 'git_reconciliation', 'result_recovery', 'suspended_tasks', 'blocker'))):
                raise ValueError('suspended task needs its original identity and no pending transaction')
            pending[key] = dict(saved, phase='recover', in_flight=False,
                                consolidation_obligations=obligations,
                                queue_before=after, queue_structure=plan.structure(selected=key),
                                stage_baseline=baseline, protected_staged=staged)
            if transfer:
                record = task_record(task)
                pending[key].update(record, task=record)
                pending[key]['handoff'] = (saved.get('handoff', '')
                    + '\nReviewed plan split: follow the current brief and cross-plan scope owners. '
                    'Original results, unfinished acceptance and session counts remain retained; '
                    'this administrative operation grants no task completion.')
            if key in merges.values():
                record = task_record(task)
                pending[key].update(record, task=record)
                pending[key]['handoff'] = (saved.get('handoff', '')
                    + '\nExplicit consolidation preserves all original obligations. '
                    'Complete acceptance for every target in the combined brief; no completion credit was granted.')
            validate_task_metadata(plan, pending[key])
        for saved in (state, *pending.values()):
            if any(type(saved.get(field, 0)) is not int or saved.get(field, 0) < 0
                   for field in ('total_sessions', 'task_sessions', 'session_limit', 'repair_sessions')):
                raise ValueError('retained session counts are malformed')
            if saved.get('task'):
                task_session_usage(saved)
        updated = dict(phase='complete', in_flight=False, task_id=None, task_sessions=0,
                       consolidation_obligations=obligations,
                       total_sessions=state.get('total_sessions', 0),
                       queue_before=after, queue_structure=plan.structure(),
                       suspended_tasks=pending, replan_baseline=baseline, protected_staged=staged,
                       handoff='Resume the first unchecked task in the reconciled plan. '
                               'Unresolved work remains subject to each task\'s acceptance.\n'
                               + state.get('handoff', ''),
                       reconciliation=dict(source_run=identity, checkpoint_sha256=hashlib.sha256(raw).hexdigest(),
                           head=git_output(root, 'rev-parse', '--verify', 'HEAD').stdout.strip()))
        if merges:
            updated['reconciliation'].update(merge_tasks=list(merge_tasks), base=base)
        if transfer:
            updated['reconciliation'].update(split=transfer, base=base)
        for task in tasks:
            if not task.complete:
                validate_consolidated_metadata(task_record(task), obligations)
        plan.validate_recovery(updated)
        if not check:
            launcher.finish_nested(root, run)
            backup = run / ('checkpoint-before-reconcile-' + updated['reconciliation']['checkpoint_sha256'] + '.json')
            archived = {'checkpoint_utf8': raw.decode('utf-8')}
            if os.path.lexists(backup):
                info = backup.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1
                        or json.loads(backup.read_bytes()) != archived):
                    raise ValueError('reconciliation backup changed; preserve the checkpoint')
            else:
                launcher.atomic(backup, archived)
            launcher.atomic(checkpoint, updated)
        return dict(run=identity, next_task=plan.next_task().id if plan.next_task() else None,
                    reconciled=not check, checked=check)


def closeout(plan, spec, run, state):
    with closeout_lock(plan.root, run, state):
        try:
            return _closeout(plan, spec, run, state)
        except SessionResultRejected as error:
            state.update(phase='recover', in_flight=False, plan_queue=plan.queue)
            retain_result_rejection(run, error, label=spec.name, checkpoint=state)
            state.pop('pending_completion', None)
            launcher.atomic(run / 'checkpoint.json', state)
            return False
        except GitReconciliationRequired as error:
            result = state['pending_completion']
            reconciliation = state.get('git_reconciliation', {})
            identity = state.get('pull_intent') or reconciliation
            state.update(phase='recover', in_flight=False, plan_queue=plan.queue,
                         git_reconciliation={**reconciliation, 'reason': str(error), 'accepted_result': result,
                                             **{key: identity[key] for key in ('branch', 'upstream')
                                                if key in identity}},
                         handoff=str(error) + '\n' + result['handoff'])
            if isinstance(error, OwnershipReconciliationRequired):
                state['git_reconciliation']['ownership_paths'] = error.paths
            state.pop('pending_completion', None)
            launcher.atomic(run / 'checkpoint.json', state)
            return False


def _closeout(plan, spec, run, state):
    result = state['pending_completion']
    if not state.get('pull_intent'):
        validate_session_result(result, lambda result: validate_result(plan, state, result))
    launcher.finish_nested(plan.root, run)
    # The task owns its checks. Keep its result in the existing checkpoint;
    # disposable diagnostics and historical links are not close-out prerequisites.
    if spec.commit_prefix:
        paths = state.get('commit_intent', {}).get('paths')
        state['plan_queue'] = plan.queue
        if paths is None:
            paths = list(dict.fromkeys([*result['stage_paths'], plan.path, plan.queue]))
            validate_closeout_ownership(plan.root, paths, state)
        pull_before_commit(plan.root, run, state, git=git_output)
        # A pull may have changed plan metadata. Reapply every guard before
        # staging, even when Git reports an already-up-to-date branch.
        validate_session_result(result, lambda result: validate_result(plan, state, result))
        if state.get('commit_intent') is None:
            paths = stage_task(plan.root, paths, required_paths=(plan.path, plan.queue))
        commit_push_propagate(plan.root, run, state, paths,
                              f"{spec.commit_prefix}: Completed task {state['task_id']}", git=git_output)
    state.update(phase='complete', in_flight=False, summary=result['summary'], handoff=result['handoff'])
    state.pop('pending_completion', None)
    state.pop('commit_intent', None)
    state.pop('pull_intent', None)
    state.pop('git_reconciliation', None)
    state.pop('worktree_propagation', None)
    launcher.atomic(run / 'checkpoint.json', state)
    return True


def load_plan(root, path, state):
    if any(state.get(key) for key in ('git_reconciliation', 'pull_intent', 'result_recovery',
                                     'evidence_renewal')):
        # The pull itself can leave conflicts in the master/queue. Retain their
        # validated identities so a restart can resolve them before parsing.
        master = local_path(root, path)
        queue = local_path(root, state['plan_queue'])
        return Plan(root.resolve(), str(master.relative_to(root.resolve())),
                    str(queue.relative_to(root.resolve())))
    return Plan.load(root, path)


def execute(root, spec, run, owner):
    error_path = run / 'agent-error.json'
    error_path.unlink(missing_ok=True)
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
        if error_path.exists():
            error = json.loads(error_path.read_text())
            if (status == 75 and error.get('context') == 'turn failed'
                    and error.get('codex_error_info') == 'serverOverloaded'):
                raise AgentCapacityUnavailable(error['message'])
            raise ValueError(error['message'])
        raise ValueError(f'agent session exited {status}; inspect retained output and handoff')
    return read_session_result(run)


RESPONSE_VALIDATOR_SOURCES = (
    'plan_launcher.py', 'execution_plan.py', 'document_checks.py',
    'launcher_runtime.py', 'detached_launcher.py',
    'launcher_reload.py',
    'launcher_observer.py', 'launcher_view.py', 'launcher_display.py', 'launcher_progress.py',
    'launcher_session.py', 'launcher_chat.py', 'launcher_render.py', 'watch_output.py',
    # Shared storage retirement still protects owned resources and any older
    # required captures. These guards do not collect task archives.
    'test_retention.py', 'test_storage.py', 'test_io.py', 'test_input_transfer.py',
    'evidence_capture.py', 'evidence_identity.py', 'capture_publication.py',
    'evidence_bundle.py', 'recording_storage.py', 'artifact_export.py',
    'launcher_git.py', 'launcher_worktrees.py', 'launcher_question.py',
    'plan_reconciliation.py', 'vm_selection.py', 'vm_pool.py',
    '../tests/integration/vm_config.py', 'plan_response.schema.json',
)

def response_validator_sources():
    """Detect repairs that this process cannot load by retrying an agent turn."""
    sources = {}
    for name in RESPONSE_VALIDATOR_SOURCES:
        try:
            sources[name] = hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        except FileNotFoundError:
            # A parallel refactor can remove an old controller's dependency.
            # Let the fresh controller load its own inventory at the boundary.
            sources[name] = None
    return sources


def reload_controller(root, run, owner, spec):
    """Replace imports without releasing ownership, scratch leases or the run."""
    descriptors = (owner, *launcher.scratch_descriptors())
    replace_interpreter(['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
        '--reload-worker', str(root), str(run), str(owner), json.dumps(asdict(spec))], descriptors)


def worker(root, run, owner, spec, state, *, reloading=False):
    from launcher_chat import task_info_instructions

    def heading():
        return task_heading(state['task_id'], state['title'], Path(state['brief']))

    def completed_task():
        budget.complete()
        started = state.get('started_at')
        duration = time.time() - started if started is not None else None
        publish_completion(run, state['task_id'], heading(), duration, [state['task_id']])

    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: (run / 'cancel').touch(mode=0o600))
    budget = TaskBudget(run)
    status, reason = 0, 'queue complete'
    reload = False
    try:
        # exec retains ownership and this live checkpoint. Reloading code is
        # not a fresh admission: continue without replaying startup validation.
        plan = load_plan(root, spec.plan, state)
        state.setdefault('selected_tasks', list(state.get('queue_before') or plan.state()))
        refresh_live_plan(plan, state)
        reload_request = ReloadRequest(run)
        reload_reason = ('manual reload requested; '
                         'reloading controller and continuing the retained handoff')
        if state.get('recovery_run'):
            launcher.finish_nested(root, Path(state['recovery_run']))
        if reloading and (run / 'cancel').exists():
            raise launcher.Stopped()
        if state.get('pending_completion') and not (reloading and (run / 'stop').exists()):
            publish_progress(run, state['task_id'], [heading(), 'Recovering accepted task close-out…'])
            if closeout(plan, spec, run, state):
                completed_task()
                print(f"{spec.name}: recovered task {state['task_id']} close-out.", flush=True)
        while True:
            if (run / 'cancel').exists():
                raise launcher.Stopped()
            if (run / 'stop').exists():
                reason = 'stopped at a session boundary'
                break
            # A valid continuation can need new startup recovery just as a
            # rejected response can need repaired guards. Never spend another
            # session, select another task or wait for an answer under old code.
            if reload_request.pending():
                reload, reason = True, reload_reason
                break
            plan = load_plan(root, spec.plan, state)
            refresh_live_plan(plan, state)
            recovery = state.get('capacity_recovery')
            if capacity_retry(state):
                delay = recovery['retry_after'] - time.time()
                if delay > 0:
                    time.sleep(min(1, delay))
                    continue
            completed_state = None
            if state['phase'] == 'complete':
                task = next((task for task in plan.tasks(selected=state['selected_tasks'])
                             if not task.complete), None)
                if task is None:
                    reason = 'queue complete'
                    break
                limits = budget.read()
                if limits.get('closed') or (limits['tasks'] is not None
                        and limits['completed'] >= limits['tasks']):
                    reason = 'task limit reached'
                    break
                completed_state = state
                pending = dict(state.get('suspended_tasks', {}))
                inherited_baseline = state.get('replan_baseline')
                inherited_staged = state.get('protected_staged')
                if task.id in pending:
                    selected = dict(pending.pop(task.id))
                    validate_task_metadata(plan, selected)
                    selected.update(total_sessions=state.get('total_sessions', 0),
                                    queue_before=plan.state(selected=state['selected_tasks']),
                                    queue_structure=plan.structure(selected=task.id))
                else:
                    selected = dict(task_record(task), task=task_record(task), phase='implement',
                             task_sessions=0, total_sessions=state.get('total_sessions', 0),
                             repair_sessions=0,
                             session_limit=spec.max_sessions,
                             stage_baseline=inherited_baseline if inherited_baseline is not None else worktree_snapshot(root),
                             protected_staged=inherited_staged if inherited_baseline is not None else
                                list(filter(None, git_output(root, 'diff', '--cached', '--name-only', '-z').stdout.split('\0'))),
                             queue_before=plan.state(selected=state['selected_tasks']),
                             queue_structure=plan.structure(selected=task.id))
                if pending:
                    selected.update(suspended_tasks=pending, replan_baseline=selected['stage_baseline'])
                if state.get('consolidation_obligations'):
                    selected['consolidation_obligations'] = state['consolidation_obligations']
                selected['selected_tasks'] = state['selected_tasks']
                state = selected
            if state['phase'] == 'blocked':
                launcher.atomic(run / 'chat-state.json', {'session': state.get('total_sessions'),
                    'task_id': state['task_id'], 'task_session': state['task_sessions'], 'status': 'blocked'})
                answer = wait_for_answer(run, state['blocker'], state['blocker_id'],
                    state['task_id'], label=spec.name, heading=f"Task {state['task_id']}: {state['title']}",
                    on_poll=reload_request.check)
                if answer is None:
                    reason = 'stopped at a session boundary'
                    break
                state['answer'] = answer
                state['phase'] = 'recover'
                state['session_limit'] = max(state['session_limit'], task_session_usage(state) + 1)
                # Waiting can outlive a repair; retain the answer for the fresh
                # controller instead of starting a turn under the old imports.
                if reload_request.pending():
                    reload, reason = True, reload_reason
                    break
            retrying_capacity = capacity_retry(state)
            if not retrying_capacity and not budget.admit():
                if completed_state is not None:
                    state = completed_state
                reason = 'task limit reached'
                break
            if not retrying_capacity:
                state['session_kind'] = 'repair' if coordinator_repair(state) else 'task'
                used = task_session_usage(state)
                if state['session_kind'] == 'repair':
                    if state.get('repair_sessions', 0) >= MAX_REPAIR_SESSIONS:
                        status, reason = 1, 'coordinator repair session limit reached; retain the task and repair handoff'
                        break
                elif used >= state['session_limit']:
                    status, reason = 1, 'task session limit reached; resume with a fresh run'
                    break
            if state.get('git_reconciliation'):
                try:
                    validate_pull_identity(root, state, git=git_output)
                except GitReconciliationRequired as error:
                    state['git_reconciliation']['reason'] = str(error)
            if spec.commit_prefix:
                # Retained/replanned baselines can predate an external reviewed
                # commit. Release clean paths before the agent dirties them,
                # while their worktree, mode and index still prove ownership.
                validate_closeout_ownership(root, [], state)
            state.setdefault('started_at', time.time())
            active_spec = capacity_session_spec(spec, state)
            if not retrying_capacity:
                state.pop('capacity_recovery', None)
                state['task_sessions'] += 1
                if state['session_kind'] == 'repair':
                    state['repair_sessions'] = state.get('repair_sessions', 0) + 1
                state['total_sessions'] += 1
            # Clear the preceding response before publishing a new in-flight turn,
            # so restart recovery cannot adopt a stale response for this task.
            (run / 'agent-result.json').unlink(missing_ok=True)
            # A genuine no-tool turn still has an exact empty command record.
            # Never truncate the retained history from earlier task sessions.
            with (run / 'agent-commands.log').open('ab'):
                pass
            state['in_flight'] = True
            remaining = sum(not done for done in state['queue_before'].values())
            budget.update(lambda value: value.update(remaining=remaining + value['completed']))
            launcher.atomic(run / 'checkpoint.json', state)
            (run / 'prompt.txt').write_text(session_prompt(plan, active_spec, state)
                                           + task_info_instructions(run, state['task_id']))
            launcher.atomic(run / 'nested.json', [])
            (run / 'nested-closed').unlink(missing_ok=True)
            publish_progress(run, state['task_id'], session_lines(heading(),
                state['task_sessions'], active_spec.model, active_spec.effort))
            try:
                result = execute(root, active_spec, run, owner)
                plan = load_plan(root, spec.plan, state)
                if state['task_id'] not in plan.state(selected=state['selected_tasks']):
                    launcher.finish_nested(root, run)
                    refresh_live_plan(plan, state)
                    launcher.atomic(run / 'checkpoint.json', state)
                    continue
                validate_session_result(result, lambda result: validate_result(plan, state, result))
            except AgentCapacityUnavailable as error:
                launcher.finish_nested(root, run)
                failures = state.get('capacity_recovery', {}).get('failures', 0) + 1
                delay, fallback, exhausted = capacity_failure(spec.model, failures, delays=CAPACITY_RETRY_DELAYS)
                state.update(phase='recover', in_flight=False, capacity_recovery={
                    'message': str(error), 'retry_after': time.time() + delay,
                    'session': state['total_sessions'], 'failures': failures, 'exhausted': exhausted})
                launcher.atomic(run / 'checkpoint.json', state)
                if exhausted:
                    status, reason = 1, f'model capacity recovery exhausted: {error}'
                    break
                if fallback:
                    print(f'{spec.name}: model still at capacity; using gpt-6-astra '
                          f'{spec.effort} for this session only.', flush=True)
                else:
                    print(f'{spec.name}: model at capacity; retrying this session after '
                          f'{delay} seconds.', flush=True)
                continue
            except SessionResultRejected as error:
                launcher.finish_nested(root, run)
                state.pop('capacity_recovery', None)
                state.update(phase='recover', in_flight=False, plan_queue=plan.queue)
                retain_result_rejection(run, error, label=spec.name, checkpoint=state)
                launcher.atomic(run / 'checkpoint.json', state)
                continue
            launcher.finish_nested(root, run)
            state.pop('result_recovery', None)
            state.pop('capacity_recovery', None)
            state.update(summary=result['summary'], handoff=result['handoff'], in_flight=False)
            if result['status'] == 'task_complete' and state.get('git_reconciliation'):
                # The coordinator has reconciled and renewed acceptance. The
                # next close-out must pull again before making a fresh commit.
                if not state.get('commit_intent'):
                    state.pop('pull_intent', None)
            if result['status'] == 'task_complete':
                state['pending_completion'] = result
                launcher.atomic(run / 'checkpoint.json', state)
                if closeout(plan, spec, run, state):
                    completed_task()
            elif result['status'] == 'blocked':
                state.update(phase='blocked', blocker=result['blocker'], blocker_id=uuid.uuid4().hex)
            elif prerequisite_handoff(plan, state, result):
                consumer, title = state['task_id'], heading()
                state = defer_to_prerequisite(plan, state)
                publish_progress(run, consumer, [title])
            else:
                state['phase'] = 'recover'
            launcher.atomic(run / 'checkpoint.json', state)
    except ReloadRequested:
        reload, reason = True, reload_reason
    except launcher.Stopped:
        status, reason = 130, 'cancelled after owned cleanup'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        status, reason = 1, str(error)
    finally:
        try:
            try:
                launcher.finish_shutdown(root, run)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                reload, status, reason = False, 1, f'owned cleanup failed: {error}'
            if reload and (run / 'cancel').exists():
                reload, status, reason = False, 130, 'cancelled after owned cleanup'
            elif reload and (run / 'stop').exists():
                reload, reason = False, 'stopped at a session boundary'
            state['reason'] = reason
            launcher.atomic(run / 'checkpoint.json', state)
            (run / 'handoff.txt').write_text(state.get('handoff', '') + '\n' + reason + '\n'
                                           + result_recovery_instructions(state.get('result_recovery'),
                                               allowance='separate coordinator repair allowance'))
            print(f'{spec.name}: {reason}.', flush=True)
            if reload:
                try:
                    reload_controller(root, run, owner, spec)
                except OSError as error:
                    status, reason = 1, f'controller reload failed: {error}; resume with a fresh run'
                    state['reason'] = reason
                    launcher.atomic(run / 'checkpoint.json', state)
                    with (run / 'handoff.txt').open('a') as handoff:
                        handoff.write(reason + '\n')
                    print(f'{spec.name}: {reason}.', flush=True)
            budget.close()
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
    parser.add_argument('--reconcile', metavar='RUN',
                        help='adopt a reviewed committed replan for an inactive retained run; no task execution')
    parser.add_argument('--propagation-head', metavar='COMMIT',
                        help='with --reconcile: acknowledge reviewed destination restoration at this full HEAD; retain stash')
    parser.add_argument('--merge-task', action='append', default=[], metavar='OLD=KEEP',
                        help='explicitly consolidate an unstarted task during --reconcile; repeat for each source')
    parser.add_argument('--reconcile-base', metavar='COMMIT',
                        help='full ancestor commit matching the retained queue before consolidation or splitting')
    parser.add_argument('--split-plan', metavar='PATH',
                        help='transfer an unstarted unchecked tail to a committed plan during --reconcile')
    parser.add_argument('--revise-task', action='append', default=[], metavar='ID',
                        help='explicitly permit this unfinished scope revision during a reviewed plan split')
    add_options(parser)
    args = parser.parse_args(argv)
    if args.reload and (args.check or args.reconcile):
        parser.error('--reload cannot be combined with --check or --reconcile')
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
        if args.reconcile:
            if args.stop or args.tasks is not None or args.vm is not None:
                raise ValueError('--reconcile cannot be combined with execution, stop or VM options')
            print(json.dumps(reconcile_plan(root, spec, args.reconcile, check=args.check,
                                           merge_tasks=args.merge_task, base=args.reconcile_base,
                                           split=args.split_plan, revisions=args.revise_task,
                                           propagation_head=args.propagation_head)))
            return 0
        if args.merge_task or args.reconcile_base or args.split_plan or args.revise_task or args.propagation_head:
            raise ValueError('plan revision options require --reconcile')
        if args.check:
            plan = Plan.load(root, path)
            records = [task_record(task) for task in plan.tasks() if not task.complete]
            print(json.dumps({'plan': plan.path, 'queue': plan.queue,
                              'next_task': records[0]['task_id'] if records else None,
                              'remaining': len(records), 'model': spec.model, 'effort': spec.effort}))
            return 0
        from vm_selection import execution_selection, execution_binding, check_binding, save_binding, VARIABLE, BATCH
        binding = None
        initial = {}
        initial_info = {}
        initial_remaining = 0
        def attach(selected):
            # Omitted selection reconnects to the existing owner, whose queue
            # remains authoritative even when registry defaults have changed.
            if args.vm is not None:
                execution_selection(args.vm)
                check_binding(selected, execution_binding(), stopping=args.stop)
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
            nonlocal initial_remaining, binding
            if spec.vm or args.vm:
                execution_selection(args.vm)
            else:
                os.environ.pop(VARIABLE, None)
                os.environ.pop(BATCH, None)
            binding = execution_binding()
            previous = launcher.current_run(selected.parent)
            saved = (json.loads((previous / 'checkpoint.json').read_text())
                     if previous is not None and (previous / 'checkpoint.json').exists() else {})
            plan = load_plan(root, path, saved)
            validation_error = None
            try:
                records = [task_record(task) for task in plan.tasks() if not task.complete]
            except ValueError as error:
                validation_error = error
                records = []
            initial.update(initial_state(plan, spec, selected.parent))
            previous = launcher.current_run(selected.parent)
            if previous is not None and (previous / 'task-info.json').exists():
                initial_info.update(json.loads((previous / 'task-info.json').read_text()))
            if records or initial.get('phase') != 'complete':
                session_command(root, spec)  # Dependency/transport preflight, no model session.
            if validation_error is not None:
                if (not initial.get('in_flight') and not initial.get('pending_completion')
                        and not initial.get('git_reconciliation') and not initial.get('pull_intent')
                        and not initial.get('result_recovery') and not initial.get('evidence_renewal')
                        and not capacity_session_recovery(initial)):
                    raise validation_error
                remaining = sum(not done for done in initial['queue_before'].values())
                initial['handoff'] = (initial.get('handoff', '') + '\nReconcile interrupted close-out: ' + str(validation_error))
            else:
                remaining = len(records)
            initial_remaining = remaining
            warn_remaining(task_limit(args.tasks if args.tasks is not None else 1), remaining, label=spec.name)
            return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), '--worker',
                    str(root), str(selected), str(owner), json.dumps(asdict(spec))]
        def start(selected):
            TaskBudget(selected).initialize(args.tasks if args.tasks is not None else 1,
                                            remaining=initial_remaining)
            launcher.atomic(selected / 'checkpoint.json', initial)
            if initial_info:
                launcher.atomic(selected / 'task-info.json', initial_info)
            save_binding(selected, binding)
        from launcher_view import WorkflowView, plan_view
        view = plan_view(root, path)
        with ExitStack() as observer:
            display = None
            def prepare(selected):
                nonlocal display
                # Paint before startup validation; keep Ctrl+C available.
                display = observer.enter_context(WorkflowView().display(sys.stdout, selected))
                display.update([{'key': 'startup', 'lines': [
                    f'{spec.name}: resuming task queue…']}], [])
            run, started = launcher.select(root, 'plans', command, stop=args.stop, stop_marker='stop',
                                           on_attach=attach, on_start=start, on_prepare=prepare,
                                           namespace=plan_namespace(path), resumable_start=True,
                                           launcher_name=spec.name,
                                           **({'reload': True} if args.reload else {}))
            if run is None:
                print(f'{spec.name}: no active launcher.')
                return 0
            if interrupted:
                cancel()
            message = (f"{spec.name}: {'started' if started else 'attached to'} {run.name}; log: {run / 'output'}\n"
                       'Closing the terminal detaches. --stop waits for a session boundary. '
                       'Chat Ctrl+C interrupts; again while waiting exits.\n')
            if display is not None:
                display.attach(run, input_mode=view.input_mode)
                display.totals = view.totals
                display.write(message, saved=False)
            else:
                print(message, end='', flush=True)
            return launcher.follow(run, label=spec.name, view=view, **(
                {'display': display} if display is not None else {}))
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
    if mode in ('--worker', '--reload-worker'):
        # on_start may have saved active/suspended task state in this newly
        # registered run after command construction. Its checkpoint,
        # rather than the earlier argv snapshot, is the worker's input.
        initial = json.loads((run / 'checkpoint.json').read_text())
        sys.exit(worker(root, run, owner, spec, initial, **(
            {'reloading': True} if mode == '--reload-worker' else {})))
    if mode == '--supervise':
        try:
            status = launcher.supervise(root, run, owner, 'agent', session_command(root, spec, run),
                                       nested=True, interactive=True, hide_task_completion=True,
                                       capacity_recovery=False)  # The resumable controller owns these retries.
        except AgentCapacityUnavailable:
            status = 75  # Only after supervisor process and nested cleanup succeeded.
        sys.exit(status)
    raise SystemExit('private execution-plan worker entry point')
