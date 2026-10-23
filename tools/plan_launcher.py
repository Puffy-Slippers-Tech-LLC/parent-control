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
import plan_evidence
import plan_evidence_recovery
from execution_plan import Plan, Task, local_file, local_path, plan_namespace
from launcher_git import (GitReconciliationRequired, closeout_lock, finish_commit, git_output, propagate_worktrees,
                          pull_before_commit, reconciliation_instructions, stage_task,
                          validate_closeout_ownership, validate_pull_identity, worktree_snapshot)
from launcher_progress import publish_progress
from launcher_question import BLOCKER_INSTRUCTIONS, validate_blocker, wait_for_answer
from launcher_runtime import (AgentCapacityUnavailable, SessionResultRejected, TaskBudget, add_options, capacity_retry,
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
    push: bool = True
    vm: bool = False
    max_sessions: int = 5


CAPACITY_RETRY_DELAYS = (5, 10, 20, 40, 80)


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
    if result['status'] == 'blocked':
        validate_blocker(result['blocker'])
    elif result['blocker'] is not None:
        raise ValueError('only a blocked result may carry a developer question')
    if result['status'] == 'task_complete':
        validate_consolidated_metadata(state['task'], state.get('consolidation_obligations', {}))
        required = state['task']['acceptance']
        targets = state['task']['targets'] or ['']
        if (not result['cleanup_complete'] or not result['checks']
                or any(check['result'] != 'passed' or not check['evidence'].strip() for check in result['checks'])
                or any(not any(check['kind'] == required and check['target'] == target
                               for check in result['checks']) for target in targets)):
            raise ValueError('completion requires passing scoped acceptance evidence and owned cleanup')


def prerequisite_handoff(plan, state, result):
    """Recognize a safe insertion without requiring a corrective status-only turn."""
    return (result['status'] == 'prerequisite_required'
            or result['status'] == 'continue' and result['cleanup_complete']
            and plan.prerequisite_repair(state) is not None)


def validate_result(plan, state, result):
    if Plan.load(plan.root, plan.path).queue != plan.queue:
        raise ValueError('master plan queue changed since its checkpoint; reconcile the retained handoff')
    validate_result_payload(state, result)
    validate_task_metadata(plan, state)
    try:
        plan_evidence.consume(plan, state, result, register=False)
    except plan_evidence.EvidenceUnavailable:
        # Exact absence is renewed by closeout; context, integrity and authority
        # failures remain ordinary response refusals, never missing proof.
        pass
    complete = result['status'] == 'task_complete'
    if prerequisite_handoff(plan, state, result):
        if state.get('git_reconciliation'):
            raise ValueError('Git reconciliation must finish the retained task before selecting prerequisites')
        if not result['cleanup_complete'] or plan.prerequisite_repair(state) is None:
            raise ValueError('prerequisite handoff needs a valid backward dependency insertion and owned cleanup')
        return
    if complete:
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
Read AGENTS.md, docs/Execution-Plans.md, master {plan.path}, ordered queue
{plan.queue}, and the selected brief
{state['task']['brief']}; follow only applicable owning contracts and source.
Use these exact checkout-relative paths. Resolve other document links relative
to their containing document; do not infer filenames from titles or launcher names.
Your coordinator model for this session is {spec.model} {spec.effort}.
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
handoff. At close-out, you may update this row's Estimate with timing/evidence;
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
result. Reconcile its retained evidence and cleanup, complete missing work or
restore its unchecked row/brief/pointer before returning continue or blocked.
{BLOCKER_INSTRUCTIONS}
Return the required JSON response.
Each checks item names kind, one declared canonical target (empty only when the
brief declares no Targets), actual
passed/failed/not_run result and exact retained evidence or review findings.
For a runner-issued structured handoff, use a JSON string as checks[].evidence:
schema "onpc-plan-evidence", version 1, and the exact reference, consumer and
record objects returned by the producer. Select one declared member and retain
its original target, inputs, attempt, verdict and cleanup. Do not invent those
objects or replace installed acceptance with diagnostic proof. Legacy exact
report paths remain supported when no structured handoff is available.
Never report task_complete unless every required check passed and cleanup ended.
Previous handoff/recovery: {state.get('handoff', 'No prior session.')}
Verified closed-turn records: {json.dumps(state.get('evidence_turns', []))}
{('The preceding turn ended because the provider was at capacity. Reconcile partial '
  'work and retained command/test results after owned cleanup, then continue this '
  'same task and session. No acceptance or extra task-session allowance was granted. Failure: '
  + state['capacity_recovery']['message']) if state.get('capacity_recovery') else ''}
Developer answer: {json.dumps(state.get('answer'))}
Original consolidated obligations: {json.dumps(state.get('consolidation_obligations', {}).get(state['task_id'], []))}
For a consolidated task, every original scope and per-target acceptance assertion
above remains required. The current combined brief replaces only the former
single-target scheduling and queue close-out instructions.
{reconciliation_instructions(state)}
{result_recovery_instructions(state.get('result_recovery'))}
{('Acceptance evidence expired before publication. Inspect the exact retained '
  'response, command record and captured task inputs at '
  + state['evidence_renewal']['evidence_source']['path'] + '. '
  + state['evidence_renewal']['reason'] + '\n'
  'Preserve the task, queue baseline, suspended consumers, acceptance targets '
  'and Git ownership. Reuse verified surviving proof and rerun checks whose '
  'detailed proof is lost. The checkpoint retains any applied evidence-recovery '
  'transaction; do not reapply it or invent an expired receipt. Restore the '
  'captured brief and unchecked row/pointer if returning continue. Return a '
  'new result with exact available evidence before close-out.\n')
 if state.get('evidence_renewal') else ''}
{('The temporary brief is missing and no exact earlier brief snapshot was retained. '
  'Restore the authorized brief and return continue with the task unchecked. '
  'The next session must capture its exact restored input before completion; '
  'do not report task_complete in this restoration session.')
 if state.get('evidence_capture_requires_brief') else ''}
"""


def validate_consolidated_metadata(record, obligations):
    originals = obligations.get(record['task_id'], [])
    if originals and (any(item['acceptance'] != record['acceptance'] for item in originals)
            or set(record['targets']) != {target for item in originals for target in item['targets']}):
        raise ValueError('consolidated task must retain its original acceptance kind and all targets')


def validate_task_metadata(plan, state):
    """A fresh session must not silently reuse weaker saved acceptance targets."""
    brief = Path(state['task']['brief'])
    if not brief.exists() and (state.get('in_flight') or state.get('pending_completion')
                               or state.get('git_reconciliation') or capacity_session_recovery(state)):
        return  # Recovery may restore a brief removed during partial close-out.
    brief = local_file(plan.root, str(brief.relative_to(plan.root)))
    current = task_record(Task(state['task_id'], False, state['title'], brief, ()))
    validate_consolidated_metadata(current, state.get('consolidation_obligations', {}))
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
    plan_evidence.recover(plan)
    previous = launcher.current_run(directory)
    if previous and (previous / 'checkpoint.json').exists():
        state = json.loads((previous / 'checkpoint.json').read_text())
        if capacity_session_recovery(state) and not reloading:
            state['capacity_recovery']['restart'] = True
        state = plan_evidence_recovery.recover_evidence(
            plan, state, previous,
            verify_proof=lambda correction, request: plan_evidence_recovery.verify_proof(
                plan, correction, request),
            read_authorization=lambda request: plan_evidence_recovery.read_authorization(plan, request),
            verify_only=reloading)
        if (state.get('consolidation_obligations') and not any(
                state.get(key) for key in ('in_flight', 'pending_completion',
                                          'git_reconciliation', 'pull_intent', 'result_recovery',
                                          'evidence_renewal'))):
            for task in plan.tasks():
                if not task.complete:
                    validate_consolidated_metadata(task_record(task), state['consolidation_obligations'])
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
                    saved['session_limit'] = saved.get('task_sessions', 0) + spec.max_sessions
        if state.get('phase') != 'complete':
            if not any(state.get(key) for key in ('git_reconciliation', 'pull_intent', 'result_recovery',
                                                 'evidence_renewal')):
                try:
                    plan.validate_recovery(state)
                except ValueError:
                    if plan.prerequisite_repair(state) is None:
                        raise
                    if not capacity_session_recovery(state):
                        state = defer_to_prerequisite(plan, state)
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
            plan.validate_recovery(state)
            state['recovery_run'] = str(previous)
            return state
        if reloading:
            if state.get('queue_before'):
                plan.validate_recovery(state)
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
                   split=None, revisions=()):
    """Explicitly adopt a committed replan, preserving the inactive checkpoint.

    This administrative operation executes no task and grants no acceptance.
    A checked row must already have been accepted and recorded in Git.
    """
    from test_storage import directory as storage_directory
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
                   for field in ('total_sessions', 'task_sessions', 'session_limit')):
                raise ValueError('retained session counts are malformed')
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
        return _closeout(plan, spec, run, state)


def _closeout(plan, spec, run, state):
    result = state['pending_completion']
    if not state.get('pull_intent'):
        validate_result(plan, state, result)
    # Acceptance must outlive the disposable model session, including a later
    # interrupted Git transaction. Close nested owners before recording cleanup.
    launcher.finish_nested(plan.root, run)
    try:
        index = plan_evidence.preserve(plan, run, state, result)
    except plan_evidence.EvidenceUnavailable as error:
        if any(state.get(key) for key in ('commit_intent', 'pull_intent', 'git_reconciliation')):
            raise  # Never renew acceptance across an unfinished Git transaction.
        plan_evidence._source(plan, run, state, result)
        state.update(phase='recover', in_flight=False, plan_queue=plan.queue,
                     evidence_renewal=dict(reason=str(error), result=result,
                                          evidence_source=state['evidence_source']),
                     handoff=result['handoff'] + '\n' + str(error))
        state.pop('pending_completion')
        state.pop('evidence_source')
        launcher.atomic(run / 'checkpoint.json', state)
        print(f'{spec.name}: {error} Returning to the coordinator within the existing '
              'session limit; no task accepted.', flush=True)
        return False
    state.pop('evidence_renewal', None)  # Exact renewed proof is now durably verified.
    plan_evidence.rewrite_references(plan, state, index)
    validate_result(plan, state, result)
    if spec.commit_prefix:
        paths = state.get('commit_intent', {}).get('paths')
        if paths is None:
            paths = list(dict.fromkeys(result['stage_paths']))
            validate_closeout_ownership(plan.root, paths, state)
        state['plan_queue'] = plan.queue
        try:
            pull_before_commit(plan.root, run, state, git=git_output)
        except GitReconciliationRequired as error:
            identity = state.get('pull_intent', {})
            state.update(phase='recover', in_flight=False,
                         git_reconciliation=dict(reason=str(error), accepted_result=result,
                                                 **{key: identity[key] for key in ('branch', 'upstream')
                                                    if key in identity}),
                         handoff=str(error) + '\n' + result['handoff'])
            state.pop('pending_completion', None)
            state.pop('pull_intent', None)
            launcher.atomic(run / 'checkpoint.json', state)
            return False
        # A pull may have changed plan metadata. Reapply every guard before
        # staging, even when Git reports an already-up-to-date branch.
        validate_result(plan, state, result)
        if state.get('commit_intent') is None:
            paths = stage_task(plan.root, paths, required_paths=(plan.path, plan.queue))
        committed = finish_commit(plan.root, run, state, paths,
                                  f"{spec.commit_prefix}: Completed task {state['task_id']}")
        if spec.push:
            if state.get('pull_intent') is not None:
                _, head = validate_pull_identity(plan.root, state, git=git_output)
                if (committed is not None and head != committed
                        and git_output(plan.root, 'merge-base', '--is-ancestor', committed,
                                       head, check=False).returncode):
                    raise ValueError('HEAD changed after completion commit; inspect retained checkpoint before push')
            pushed = git_output(plan.root, 'push', check=False)
            if pushed.returncode:
                raise ValueError('completion push failed: ' + pushed.stderr.strip())
            propagate_worktrees(plan.root, run, state, committed, git=git_output)
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
    'launcher_runtime.py', 'plan_evidence.py', 'plan_evidence_recovery.py',
    'evidence_bundle.py', 'detached_launcher.py',
    # Explicit retained-decision closure audited in Export-Design.md. Storage
    # locks include input-transfer admission; helper dispatch authenticates the
    # owner before preservation, and Git/question/reconciliation retain state.
    'test_retention.py', 'test_storage.py', 'test_input_transfer.py',
    'launcher_git.py', 'launcher_worktrees.py', 'onpc-test-artifacts', 'launcher_question.py',
    'plan_reconciliation.py', 'vm_selection.py', 'vm_pool.py', '../tests/integration/vm_config.py',
    'evidence_identity.py', 'evidence_capture.py', 'capture_publication.py',
    'recording_storage.py', 'artifact_export.py',
    # Runner terminal records now supply the exact provenance retained by
    # evidence consumers; reload before accepting decisions from changed code.
    'runner_evidence.py', 'regression.py', 'regression_process.py',
    'regression_events.py', 'test_commands.py', 'vm_test_queue.py',
    'regression_inputs.py',
    'test_recovery.py',
    # Qualification and collector producers determine the retained result,
    # candidate and true outer cleanup provenance.
    '../tests/integration/qualification_storage.py',
    '../tests/integration/system_runner.py', '../tests/integration/vm_probe.py',
    '../tests/integration/baseline_guest.py',
    '../tests/integration/check_graphical_recovery.py',
    '../tests/integration/check_graphical_smoke.py', '../tests/integration/check_e2e_watch.py',
    '../tests/e2e/private_artifacts.py', '../tests/e2e/execution.py', '../tests/e2e/e2e_worker.py',
    'onpc-test-runner', '../tests/e2e/runner.py',
    '../tests/integration/guest_inputs.py', '../tests/integration/owned_commands.py',
    '../tests/e2e/evidence.py', '../tests/e2e/secret_variables.py',
)


def response_validator_sources():
    """Detect repairs that this process cannot load by retrying an agent turn."""
    return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in RESPONSE_VALIDATOR_SOURCES}


def evidence_recovery_pending(plan, state):
    """Detect a startup-only request without applying or authorizing it here."""
    if state.get('phase') == 'complete':
        return False
    request = plan_evidence_recovery.request_from_brief(plan, state)
    if request is None:
        return False
    marker = state.get('evidence_recovery')
    # Startup owns full marker/proof verification. The running controller only
    # needs to distinguish its exact already-applied request from a new one.
    return (not isinstance(marker, dict) or marker.get('request_sha256')
            != plan_evidence_recovery.digest(plan_evidence_recovery.encoded(request)))


def reload_controller(root, run, owner, spec):
    """Replace imports without releasing ownership, scratch leases or the run."""
    descriptors = (owner, *launcher.scratch_descriptors())
    inherited = {fd: os.get_inheritable(fd) for fd in descriptors}
    try:
        for fd in descriptors:
            os.set_inheritable(fd, True)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                 '--reload-worker', str(root), str(run), str(owner), json.dumps(asdict(spec))])
    finally:
        # exec only returns on failure. Preserve the ordinary finalization path.
        for fd, value in inherited.items():
            os.set_inheritable(fd, value)


def reload_state(root, run, owner, spec, state):
    """Reapply startup guards at a child-free boundary under the same owner."""
    with launcher.lock(run.parent / 'gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        identity = os.fstat(owner)
        recorded = (run.parent / 'owner').lstat()
        if (launcher.current_run(run.parent) != run
                or (identity.st_dev, identity.st_ino) != (recorded.st_dev, recorded.st_ino)
                or state.get('in_flight') or (run / 'result.json').exists()):
            raise ValueError('controller reload requires the current idle session boundary and owner')
        plan = load_plan(root, spec.plan, state)
        if evidence_recovery_pending(plan, state):
            raise ValueError('selected task has an unapplied evidence recovery request; '
                             'resume with a fresh run for inactive controller verification')
        launcher.finish_nested(root, run)
        return initial_state(plan, spec, run.parent, reloading=True)


def worker(root, run, owner, spec, state, *, reloading=False):
    from launcher_chat import task_info_instructions
    from launcher_display import clock_duration
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: (run / 'cancel').touch(mode=0o600))
    budget = TaskBudget(run)
    status, reason = 0, 'queue complete'
    reload = False
    try:
        if reloading:
            state = reload_state(root, run, owner, spec, state)
        plan = load_plan(root, spec.plan, state)
        validator_sources = response_validator_sources()
        reload_reason = ('launcher validation code changed during the session; '
                         'reloading controller and revalidating the retained handoff')
        evidence_recovery_reason = ('selected task has an unapplied evidence recovery request; '
                                    'resume with a fresh run for inactive controller verification')
        if state.get('recovery_run'):
            launcher.finish_nested(root, Path(state['recovery_run']))
        if reloading and (run / 'cancel').exists():
            raise launcher.Stopped()
        if state.get('pending_completion') and not (reloading and (run / 'stop').exists()):
            publish_progress(run, state['task_id'], [f"Task {state['task_id']}: {state['title']}",
                                                    'Recovering accepted task close-out…'])
            if closeout(plan, spec, run, state):
                budget.complete()
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
            if response_validator_sources() != validator_sources:
                reload, reason = True, reload_reason
                break
            recovery = state.get('capacity_recovery')
            if capacity_retry(state):
                delay = recovery['retry_after'] - time.time()
                if delay > 0:
                    time.sleep(min(1, delay))
                    continue
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
                validate_consolidated_metadata(task_record(task), state.get('consolidation_obligations', {}))
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
                if state.get('consolidation_obligations'):
                    selected['consolidation_obligations'] = state['consolidation_obligations']
                state = selected
            # Check after selection as well as continuations: a newly selected
            # brief can already contain a request requiring inactive ownership.
            if evidence_recovery_pending(plan, state):
                status, reason = 1, evidence_recovery_reason
                break
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
                # Waiting can outlive a repair; retain the answer for the fresh
                # controller instead of starting a turn under the old imports.
                if response_validator_sources() != validator_sources:
                    reload, reason = True, reload_reason
                    break
                if evidence_recovery_pending(plan, state):
                    status, reason = 1, evidence_recovery_reason
                    break
            retrying_capacity = capacity_retry(state)
            if not admitted and not retrying_capacity and not budget.admit():
                reason = 'task limit reached'
                break
            if not retrying_capacity and state['task_sessions'] >= state['session_limit']:
                status, reason = 1, 'task session limit reached; resume with a fresh run'
                break
            if state.get('git_reconciliation'):
                validate_pull_identity(root, state, git=git_output)
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
                state['total_sessions'] += 1
            plan_evidence.capture(plan, run, state)
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
            publish_progress(run, state['task_id'], [f"Task {state['task_id']}: {state['title']}",
                f"Session [{state['task_sessions']}]: {active_spec.model} {active_spec.effort}"])
            try:
                result = execute(root, active_spec, run, owner)
                validate_session_result(result, lambda result: validate_result(plan, state, result))
            except AgentCapacityUnavailable as error:
                launcher.finish_nested(root, run)
                failures = state.get('capacity_recovery', {}).get('failures', 0) + 1
                fallback = failures == len(CAPACITY_RETRY_DELAYS) + 1 and spec.model == 'gpt-6.1-sol'
                exhausted = failures > len(CAPACITY_RETRY_DELAYS) and not fallback
                delay = CAPACITY_RETRY_DELAYS[failures - 1] if failures <= len(CAPACITY_RETRY_DELAYS) else 0
                state.update(phase='recover', in_flight=False, capacity_recovery={
                    'message': str(error), 'retry_after': time.time() + delay,
                    'session': state['total_sessions'], 'failures': failures, 'exhausted': exhausted})
                plan_evidence.retain_turn(plan, run, state)
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
                plan_evidence.retain_turn(plan, run, state)
                launcher.atomic(run / 'checkpoint.json', state)
                continue
            # A continuation, answer or prerequisite can outlive this response's
            # run. Freeze its closed proof before another turn replaces the
            # result, prompt and nested-owner inventory.
            launcher.finish_nested(root, run)
            plan_evidence.retain_turn(plan, run, state, result)
            state.pop('result_recovery', None)
            state.pop('capacity_recovery', None)
            state.update(summary=result['summary'], handoff=result['handoff'], in_flight=False)
            if result['status'] == 'task_complete' and state.get('git_reconciliation'):
                # The coordinator has reconciled and renewed acceptance. The
                # next close-out must pull again before making a fresh commit.
                state.pop('pull_intent', None)
            if result['status'] == 'task_complete':
                state['pending_completion'] = result
                launcher.atomic(run / 'checkpoint.json', state)
                if closeout(plan, spec, run, state):
                    budget.complete()
                    duration = clock_duration(time.time() - state['started_at'])
                    publish_progress(run, 'complete-' + state['task_id'],
                        [f"\033[32m✓ Task {state['task_id']}: {state['title']} ({duration})\033[0m"],
                        replaces=[state['task_id']])
            elif result['status'] == 'blocked':
                state.update(phase='blocked', blocker=result['blocker'], blocker_id=uuid.uuid4().hex)
            elif prerequisite_handoff(plan, state, result):
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
            if reload and (run / 'cancel').exists():
                reload, status, reason = False, 130, 'cancelled after owned cleanup'
            elif reload and (run / 'stop').exists():
                reload, reason = False, 'stopped at a session boundary'
            state['reason'] = reason
            launcher.atomic(run / 'checkpoint.json', state)
            (run / 'handoff.txt').write_text(state.get('handoff', '') + '\n' + reason + '\n'
                                           + result_recovery_instructions(state.get('result_recovery')))
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
                                           split=args.split_plan, revisions=args.revise_task)))
            return 0
        if args.merge_task or args.reconcile_base or args.split_plan or args.revise_task:
            raise ValueError('plan revision options require --reconcile')
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
        initial_info = {}
        initial_remaining = 0
        initial_plan = None
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
            nonlocal initial_remaining, initial_plan
            previous = launcher.current_run(selected.parent)
            saved = (json.loads((previous / 'checkpoint.json').read_text())
                     if previous is not None and (previous / 'checkpoint.json').exists() else {})
            plan = load_plan(root, path, saved)
            initial_plan = plan
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
            # Git recovery and suspended consumers may start no model session.
            # Move their exact captured inputs forward on every registered run.
            plan_evidence.carry(initial_plan, selected, initial)
            launcher.atomic(selected / 'checkpoint.json', initial)
            if initial_info:
                launcher.atomic(selected / 'task-info.json', initial_info)
            save_binding(selected, binding)
        from launcher_view import WorkflowView, plan_progress, plan_totals
        def progress(run, steps, child_steps):
            return plan_progress(run, steps, child_steps,
                                 remaining=lambda: plan_totals(root, path)[1])
        view = WorkflowView('chat', True, progress, lambda: plan_totals(root, path))
        with ExitStack() as observer:
            display = None
            def prepare(selected):
                nonlocal display
                # Recovery can verify a large cumulative archive. Paint before
                # that work, keeping signal-based Ctrl+C until chat can poll.
                display = observer.enter_context(WorkflowView().display(sys.stdout, selected))
                display.update([{'key': 'startup', 'lines': [
                    f'{spec.name}: validating saved plan and evidence…']}], [])
            run, started = launcher.select(root, 'plans', command, stop=args.stop, stop_marker='stop',
                                           on_attach=attach, on_start=start, on_prepare=prepare,
                                           namespace=plan_namespace(path), resumable_start=True)
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
        # on_start may have moved exact active/suspended proof into this newly
        # registered run after command construction. Its published checkpoint,
        # rather than the earlier argv snapshot, is the worker's input.
        initial = json.loads(plan_evidence_recovery._read(run / 'checkpoint.json'))
        sys.exit(worker(root, run, owner, spec, initial, **(
            {'reloading': True} if mode == '--reload-worker' else {})))
    if mode == '--supervise':
        try:
            status = launcher.supervise(root, run, owner, 'agent', session_command(root, spec, run),
                                       nested=True, interactive=True, hide_task_completion=True)
        except AgentCapacityUnavailable:
            status = 75  # Only after supervisor process and nested cleanup succeeded.
        sys.exit(status)
    raise SystemExit('private execution-plan worker entry point')
