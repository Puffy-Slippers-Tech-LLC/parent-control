"""Implement one queued task at a time, handing off after a failed live VM test."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detached_launcher as launcher
from launcher_progress import (format_duration, plan_progress as task_progress,
                               plan_task_heading, publish_completion, session_lines)
from launcher_reload import ReloadRequest, ReloadRequested, replace as replace_interpreter
from launcher_question import BLOCKER_INSTRUCTIONS, validate_blocker, wait_for_answer as wait_for_developer
from launcher_runtime import (SessionResultRejected, TaskBudget, add_options, read_session_result,
                              retain_result_rejection, result_recovery_instructions, task_limit,
                              validate_session_result, warn_remaining)
from launcher_git import closeout_lock, commit_push_propagate, git_output, worktree_snapshot, session_changes


PLAN = 'docs/TestAutomation/E2E-Execution-Plan.md'
QUEUE = 'docs/TestAutomation/E2E-Task-Queue.md'
MODEL_TIERS = (('gpt-6.1-sol', 'high'), ('gpt-6.1-sol', 'xhigh'),
               ('gpt-6.1-sol', 'max'))
ADVISER_CONFIG = Path(__file__).resolve().with_name('write_e2e_adviser.toml')
MAX_TASK_SESSIONS = 5
OPTIMIZATION_INTERVAL = 3
INITIAL_PROMPT = """Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md
through host validation and the first live VM test. Close the task if it passes;
if it fails, hand off the failure to the next session.
"""
LIVE_DIAGNOSIS_INSTRUCTIONS = """Live diagnosis and repair loop:
Follow tests/README.md#live-diagnosis-before-another-repair-attempt. After an initial
scoped attempt, use a bounded source/log review to choose between a proven correction
and live investigation. When the cause remains unclear, evidence conflicts, or a
correction repeats the same failure, reproduce in an owned maintenance VM before
another speculative patch or full acceptance run. Do not wait for a fixed number
of failed rounds. A directly established mechanical cause needs no mandatory probe.
Let the failed runner finish its evidence and cleanup first; never pause or adopt
its lease. Use tools/prepare-appsnapshot --vm NAME --y --overwrite false
for a maintenance reproduction, then tools/test-vm --vm NAME exec -- COMMAND [ARG ...]
for guarded guest probes. Keep shared watch and input/identity guards active.
Engineering investigation is separate from E2E acceptance. Use whatever guest-side
inspection, debugging, temporary instrumentation and controlled state changes are
needed to establish the cause and validate a fix, including root access when useful.
Use the identity, privileges, environment and graphical/session bus context where
the failure occurs, including the non-admin child session. A successful root-shell
probe does not establish what happens in that child session. Switch or instrument
the relevant guest context as needed and observe the failing operation there.
Inspect the VM's internals directly; public-action/result restrictions on customer
acceptance do not prohibit internal probes or experiments during investigation.
Keep experiments within the owned disposable guest and maintained command routes;
record changes and recreate clean state for acceptance.
Reproduce with the shared journey/helpers, stop progression at the suspect boundary,
and keep that maintenance guest running while inspecting the actual failing state.
Name competing hypotheses and choose a probe whose result distinguishes them.
Use focused live fix experiments, comparing the original symptom and
independent result before/after one causal change. Product installation still uses
make install. Internal probes/instrumentation are diagnostic evidence, not customer
acceptance, and never authorize bypassing an input or ownership refusal.
If unresolved, continue useful live probing and live fix validation in further
rounds: refine the hypothesis/probe using new evidence, not repeated guesses.
A single inconclusive probe is not a reason to abandon live investigation.
If a bounded investigation remains unresolved but has useful next live work,
finish owned maintenance cleanup and return investigating with live_result not_run,
repair_outcome diagnostic and an empty failure_checkpoint. This is available only
after a retained failed acceptance attempt; host_validated reports actual checks.
Record actual new observations and a concrete next probe, not just plans to probe.
Do not run full acceptance merely to qualify for another session, or return stalled
while a useful authorized live experiment remains. The continuation consumes a
session but no new acceptance attempt and preserves the last formal failure.
Carry established observations, ruled-out hypotheses, exact reproduction/probe
commands, experimental changes/results, cleanup and the next discriminating live
experiment in the handoff. After session cleanup, the next coordinator recreates
the reproduction under its own maintenance ownership; it does not inherit a VM.
Keep experiments bounded within the existing session/task limits. Reasoning is
not stalled while a useful authorized probe or experiment remains available.
Codify a supported correction in maintained source/shared helpers, remove temporary
instrumentation, run affected host checks, and finish tools/test-vm --vm NAME stop
before clean live acceptance through tools/run-tests. Live experiments cannot
replace that acceptance, erase a failed attempt or change model-promotion counts.
The failed-acceptance handoff boundary still applies; maintenance experiments
investigate the previous failure before the session's acceptance attempt.
"""


def queue_state(root):
    from execution_plan import queue_state as read_queue
    return read_queue(root, PLAN, QUEUE)


def fresh_state(task):
    return {'task_id': task, 'phase': 'implement', 'live_attempts': 0,
            'task_sessions': 0, 'failed_attempts': 0, 'model_tier': 0,
            'summary': 'Implementation, host validation and the first live VM test remain.',
            'handoff': INITIAL_PROMPT, 'in_flight': False, 'stage_candidates': []}


def prerequisite_repair(root, state, before=None):
    """Recognize a backward move to explicit unfinished prerequisites, never a skip."""
    current, after = queue_state(root)
    task = state['task_id']
    order = list(after)
    if (current is None or task not in after or after[task] or current == task
            or order.index(current) >= order.index(task)):
        return False
    inserted = order[order.index(current):order.index(task)]
    if before is not None:
        if (task not in before or before[task] or current in before
                or any(after.get(key) != value for key, value in before.items())
                or [key for key in after if key in before] != list(before)
                or [key for key in after if key not in before] != inserted):
            return False
    text = (root / QUEUE).read_text().split('## Deferred future work', 1)[0]
    rows = {}
    for line in text.splitlines():
        fields = [field.strip() for field in line.split('|')]
        if len(fields) >= 6 and fields[1] in ('[ ]', '[x]'):
            rows[fields[2]] = fields
    required = set()

    def visit(key):
        row = rows.get(key)
        if row is None:
            return False
        # The canonical queue uses Baseline for tasks with no task prerequisites.
        dependencies = [] if row[4] in ('Baseline', '', '—', '-') else row[4].split(',')
        for dependency in map(str.strip, dependencies):
            if dependency not in after or order.index(dependency) >= order.index(key):
                return False
            if not after[dependency] and dependency not in required:
                required.add(dependency)
                if not visit(dependency):
                    return False
        return True

    if not visit(task) or required != set(inserted) or any(after[key] for key in inserted):
        return False
    for key in [*inserted, task]:
        link = re.fullmatch(r'\[[^\]]+\]\((E2E-Tasks/[^/]+\.md)\)', rows[key][3])
        if link is None or not ((root / QUEUE).parent / link[1]).is_file():
            return False
    return True


def select_task_state(task, state):
    """Carry suspended consumers across prerequisite completion and launcher restarts."""
    pending = dict(state.get('suspended_tasks', {}))
    selected = dict(pending.pop(task)) if task in pending else fresh_state(task)
    if pending:
        selected['suspended_tasks'] = pending
    if 'optimization' in state:
        selected['optimization'] = state['optimization']
    return selected


def resume_after_exclusion(root, state, previous):
    """Resume the queue after explicit removal of an unfinished task."""
    current, after = queue_state(root)
    task = state['task_id']
    if task in after or current is None:
        return None
    before = state.get('queue_before', {})
    text = (root / QUEUE).read_text().split('## Ordered task queue', 1)[0]
    declarations = re.findall(
        r'^Excluded tasks: \*\*(\d{3}[a-z]*(?:, \d{3}[a-z]*)*)\*\*', text, re.M)
    excluded = {item for declaration in declarations for item in declaration.split(', ')}
    removed = set(before) - set(after)
    retained = {key: done for key, done in before.items() if key in after}
    consumer = state.get('suspended_tasks', {}).get(current)
    if consumer is None and (state.get('suspended_tasks') or removed != {task}
                             or before.get(current) is not False
                             or next((key for key, done in before.items() if not done), None) != task):
        return None
    if (not removed or task not in removed or not removed <= excluded
            or not excluded.isdisjoint(after)
            or any(before[key] for key in removed)
            or retained != after or list(retained) != list(after)
            or state.get('pending_completion') or state.get('optimization_session')
            or state.get('completion_recovery') or state.get('closeout_recovery_run')
            or state.get('phase') == 'complete'
            or (consumer is not None and (
                consumer.get('pending_completion') or consumer.get('optimization_session')
                or consumer.get('completion_recovery') or consumer.get('closeout_recovery_run')
                or consumer.get('task_id') != current))):
        return None
    selected = select_task_state(current, state)
    selected.update(phase='recover', in_flight=False, recovery_run=str(previous),
                    summary=f'Resume task {current} after explicit task exclusion; '
                            'acceptance and owned cleanup still require verification.',
                    handoff=f'Resume task {current} from its current brief and scope. '
                            f'Tasks {", ".join(sorted(removed))} were explicitly excluded '
                            'by the developer; do not recreate or qualify them. '
                            'Their earlier handoffs and target requirements are superseded. '
                            f'Inspect retained results and owned cleanup in `{previous}` '
                            'before any new live work. Preserve existing code, evidence '
                            'and unrelated work. No task completion or acceptance is implied.')
    selected.pop('completion_recovery', None)
    return selected


def defer_to_prerequisite(root, state, *, recovery_run=None):
    current, _ = queue_state(root)
    pending = dict(state.get('suspended_tasks', {}))
    consumer = {key: value for key, value in state.items()
                if key not in ('suspended_tasks', 'blocker', 'blocker_id', 'queue_before', 'result_recovery')}
    consumer.update(phase='recover', in_flight=False)
    if recovery_run is not None:
        consumer['recovery_run'] = str(recovery_run)
    pending[state['task_id']] = consumer
    selected = fresh_state(current)
    selected['suspended_tasks'] = pending
    if 'optimization' in state:
        selected['optimization'] = state['optimization']
    selected['total_sessions'] = state.get('total_sessions', state.get('task_sessions', 0))
    if recovery_run is not None:
        selected.update(phase='recover', recovery_run=str(recovery_run),
                        handoff=f'Recheck retained test results and owned cleanup in `{recovery_run}`. '
                                f'Implement prerequisite `{current}` from its current brief before '
                                f'resuming incomplete task `{state["task_id"]}`. No acceptance is implied.')
    return selected


def session_progress(root, state, count):
    if state.get('optimization_session'):
        batch = state['optimization']['pending']
        return session_lines(f"Optimization: tasks {batch[0]} to {batch[-1]}",
                             state['task_sessions'], 'gpt-6.1-sol', 'high',
                             summary='lessons and reusable E2E composition')
    summary = ('Writing task code + host validation + first live VM test; close on success, hand off on failure'
               if state['phase'] == 'implement' else
               f"Investigate/fix previous failure + host validation + live VM test {state['live_attempts'] + 1}; close on success, hand off on failure")
    if state.get('diagnostic_continuation'):
        summary = 'Continue live probing/fix experiments; clean acceptance when the correction is supported'
    model, effort = session_model(state)
    return session_lines(plan_task_heading(root, QUEUE, state['task_id']),
                         state['task_sessions'], model, effort, summary=summary)


def model_tier(state):
    # Legacy unfinished checkpoints only recorded live attempts. New checkpoints
    # distinguish substantive failures from blockers and interrupted sessions.
    failed = state.get('failed_attempts', state.get('live_attempts', 0))
    return max(state.get('model_tier', 0), 1 if failed >= 2 else 0)


def session_model(state):
    if state.get('optimization_session'):
        return MODEL_TIERS[0]
    return MODEL_TIERS[model_tier(state)]


def session_command(root, state, run=None):
    model, effort = session_model(state)
    command = launcher.agent_command(
        root, model, effort, run,
        schema=Path(__file__).with_name('write_e2e_response.schema.json'),
        adviser_config=ADVISER_CONFIG if effort == 'high' and not state.get('optimization_session') else None,
        delegation=effort == 'high' and not state.get('optimization_session'))
    # Personal Fast settings must not silently spend more of the weekly budget.
    command[-1:-1] = ['-c', 'service_tier="default"', '-c', 'features.fast_mode=false']
    return command


def record_usage(run, metadata, usage):
    """Retain CLI-reported counters, never infer billing or missing child usage."""
    fields = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')
    counters = {key: usage[key] for key in fields
                if isinstance(usage, dict) and type(usage.get(key)) is int and usage[key] >= 0}
    record = dict(metadata, reported_scope='cli_turn', usage=counters or None)
    try:
        with launcher.lock(run / 'agent-usage.jsonl') as descriptor:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.lseek(descriptor, 0, os.SEEK_END)
            with os.fdopen(os.dup(descriptor), 'w', encoding='utf-8') as stream:
                stream.write(json.dumps(record) + '\n')
    except (OSError, ValueError) as error:
        # Measurement failure must not interrupt acceptance or owned cleanup.
        print(f'write-e2e: could not retain token usage: {error}', file=sys.stderr, flush=True)


def session_prompt(state):
    if state.get('optimization_session'):
        return optimization_prompt(state)
    from vm_selection import execution_instructions
    vm_instructions = execution_instructions()
    task = state['task_id']
    model, effort = session_model(state)
    label = 'GPT-6.1-Sol ' + {'high': 'High', 'xhigh': 'Extra High', 'max': 'Max'}[effort]
    model_policy = f"""You are the {label} coordinator and implementer for this session.
Own implementation, mechanical repairs, test execution and close-out.
The launcher uses GPT-6.1 Sol for implementation and advice. The shared mandatory
backend_reviewer is the sole Astra exception, only for core backend changes.
The launcher starts at Sol High, promotes to Sol Extra High after two unsuccessful
substantive live attempts, and promotes immediately after a reasoning stall or
an unsuccessful correction at the same checkpoint without meaningful progress.
Sol Extra High promotes to Sol Max on that same failed-repair/stall signal;
different failures with verified progress keep Sol Extra High. A reasoning stall
at Sol Max stops the launcher early with retained evidence. Promotion persists
across restarts and prerequisite suspension; a new task starts at Sol High.
Session counts, interruptions, external blockers and preparation alone do not
promote. Keep all acceptance, cleanup and the five-session task cap intact.
"""
    if effort == 'high':
        model_policy += """Investigate ordinary failures yourself. Delegate one bounded diagnosis
or review to the e2e_adviser agent using GPT-6.1-Sol Max only when a High repair
failed verification without improving the explanation, conflicting evidence prevents
a defensible correction, or a consequential security, concurrency or ownership
design question remains unresolved. Consult before implementing such an unresolved
risky design, including in the first session; a failed attempt is not required.
State the concrete escalation reason and what High already established.
Missing prerequisites, permissions and preparation failures use their maintained
repair or blocker routes. Do not send routine work or the whole task to the adviser.
Give it the exact question, relevant file/evidence paths, applicable contracts,
attempted corrections, user decisions and expected deliverable; use a fresh context rather than a full
conversation fork. Request concise findings, evidence, a proposed correction,
remaining uncertainty and required regressions. The adviser is read-only.
No parallel agents or overlapping work: wait for the adviser, collect its result
and close it before resuming your work or starting another consultation. The
adviser must not spawn agents, edit files, run tests, control the VM or close tasks.
You alone implement the settled correction, run all validation, own cleanup,
update the queue and return the structured result. Check advice against source
and contracts; advice is not acceptance evidence. Consult once per unresolved
question; another consultation requires materially new evidence or a distinct
question. Cosmetic rewording, another session or another failed run is not new
evidence. Carry the question, findings, attempted correction and remaining
uncertainty in the handoff so a restart does not repeat the same consultation.
Read-only access and sequential execution are not token budgets.
Apply docs/Execution-Plans.md for bounded routine delegation: plan_monitor uses
GPT-6.1 Sol Low for read-only monitoring; plan_worker uses GPT-6.1 Sol Medium for
explicitly assigned coverage refreshes. Keep the same single child slot and
sequential join/close protocol. Coverage workers may change only assigned generated
coverage assets; they never implement the repair, control VMs, run acceptance,
stage, commit or close tasks. You verify their output and own final acceptance.
"""
    else:
        model_policy += """You own the higher-effort repair directly. Ordinary delegation is disabled;
do not spawn an adviser or hand implementation back to Sol High. Use retained adviser
findings when available, checking them against current source and evidence.
"""
    common = f"""
Task {task}: follow AGENTS.md and {PLAN}, using its scoped reading routes.
Apply docs/Mandates/Test-Scope-Mandate.md before adding or restoring coverage;
do not recreate excluded non-product tests for task briefs or old qualifications.
This tools/write-e2e session stops at the phase boundary below.
{vm_instructions}

Treat staged code as the baseline. Do not analyze staged diffs or compare it to
HEAD; read current source as needed. The launcher owns staging and commits after
each completed task. Do not commit,
push, publish, invoke write-e2e/fix-tests, or access prior
Codex sessions, memories or transcripts.
Run tests through tools/run-tests for owned cancellation; preserve
ONPC_WORKFLOW_DIRECTORY. Use maintained launchers/viewers for background work
and wait for tests and owned cleanup before returning.

{model_policy}
Use only GPT-6.1 Sol for implementation, recovery and consultation. Follow the
shared mandatory backend_reviewer instructions for core backend changes.
Ignore model recommendations in older handoffs that conflict with this policy.
The launcher-selected model owns this session through validation and close-out.
Keep context focused: locate headings and symbols, then read complete relevant
sections/functions and dependencies. Reuse unchanged context; avoid whole-file
dumps and repeated broad scans. Use bounded diagnostic output and evidence paths.
Keep handoffs concise, carrying decisions and remaining work rather than transcripts.
Do not reduce required reading, assertions, validation or cleanup to save tokens.

{LIVE_DIAGNOSIS_INSTRUCTIONS}

Return the required structured result; only blockers requiring developer action
return blocked so the launcher pauses for the user's answer. Keep summary under
600 characters and handoff under 16000.
Report progress with failure_checkpoint, furthest_checkpoint and repair_outcome.
Use stable semantic checkpoint names scoped to the qualification/regression;
reuse the previous identity for the same boundary, never a timestamp, report path
or generic worker/SSH error. Record the furthest independently verified milestone
and retain its evidence in the handoff. For a failed live attempt, repair_outcome
is advanced (verified progress), diagnostic (new evidence only), or failed_repair
(a correction failed again at the same checkpoint without meaningful progress).
Only failed_repair triggers immediate promotion; diagnostic work still consumes
an unsuccessful live attempt. Explain the correction and expected/actual result
in the summary/handoff. Do not diagnose or retry a new live failure to fill these
fields: classify from already collected evidence and use diagnostic when uncertain.
If reasoning stalls with no useful authorized next step, return status stalled
and repair_outcome stalled, with the evidence and remaining uncertainty. This
may precede live execution; report the actual host/live outcome and finish owned
cleanup. The launcher promotes the next session, or stops if already Extra High.
Missing authority, external prerequisites and unresolved customer behavior remain
blocked, never stalled. For blocked or task_complete use not_applicable.
Use an empty failure_checkpoint when live_result is not failed; furthest_checkpoint
may be empty when nothing has been independently verified.
Previous progress: {json.dumps(state.get('progress'), ensure_ascii=False)}
Last formal live acceptance: {json.dumps(acceptance_evidence(state), ensure_ascii=False)}
Previous diagnostic progress: {json.dumps(state.get('diagnostic_progress'), ensure_ascii=False)}
Each checks item contains only kind (host or installed), target and actual result.
No evidence field or report reference is required.
Do not collect or renew report bundles for the launcher.
The task owns validation; a completed predecessor needs no further proof.
Return checks null when no per-check summary is needed.
{BLOCKER_INSTRUCTIONS}
Missing generated qualification assets are routine test preparation. Use the
maintained artifact builder to prepare missing named inputs, then resume validation
in this session without asking the developer. Fix missing automatic preparation
in the runner when appropriate; preserve valid existing inputs and all guards.
A preparation failure before VM access is not a failed live VM attempt and does
not trigger the live-failure handoff boundary. Repair authorized preparation
defects and retry preparation; do not count them as acceptance or advance the task.
The handoff is a standalone prompt with remaining work, task ID, exact next
commands/selectors, evidence paths, blockers and recommended model/effort.
Retain the live investigation's established and rejected hypotheses, experiment
results and next discriminating probe; do not reset to log-only guessing on resume.
Carry forward user decisions that still apply to that remaining work.
Format summary and handoff as Markdown: backticks for inline paths, selectors
and identifiers; fenced bash blocks for commands; Markdown links for references.
For task_complete, list every task-related code, test and close-out file in
stage_paths, including deletions, plan and queue. Use explicit checkout-relative
files, excluding unrelated work. Otherwise return stage_paths empty.
If a missing capability requires a queue repair, insert its unchecked prerequisite
immediately before this task, keep this task unchecked and return blocked with
live_result not_run. The launcher validates the dependency insertion and selects
that prerequisite in a fresh session without counting this task complete.
"""
    if state.get('user_answer'):
        common += ('\nThe user answered the blocker question below. Apply these instructions '
                   'to the current task while preserving its baseline and unrelated work. '
                   'Recheck the prerequisite before continuing; an answer alone is not '
                   'evidence that it passed.\n' + json.dumps(state['user_answer'], ensure_ascii=False) + '\n')
    if state.get('completion_recovery'):
        previous = state['recovery_run']
        return common + f"""
Reconcile interrupted close-out for task {task}, which is already checked in the
queue but has no valid completion response. This task remains yours; do not
implement the next unchecked task or take its pointer as acceptance evidence.
Use the existing checkpoint/handoff, current task source, recorded outcomes and
Git close-out state to finish the interrupted operation. The last safe handoff
below may predate successful checks. Preserve recorded validation and finish
only actual unfinished work and owned cleanup. Run checks that were never
completed or whose inputs changed in the current work, through maintained routes.
Missing or rotated reports require no collection, proof checking or reruns.
Reconstruct a deleted brief from the task's contracts only if unfinished scope
needs it. Do not rewrite previous run artifacts or invent a passing result.
When the task's checks and cleanup are complete, keep the queue closed and return
task_complete with verified validation outcomes and every task-owned stage_path.
The launcher will stage those files before selecting the next task.
If work remains, restore this task's unchecked row, brief and first-unchecked
pointer before continuing. A new live failure ends this session after evidence
preservation and owned cleanup, with ready_for_vm and live_result failed.
Only a prerequisite requiring developer action returns blocked; missing final
JSON alone is an automatic recovery operation, not a developer question.

Last safe handoff:
{state['handoff']}
"""
    if state['phase'] == 'implement':
        preparation = INITIAL_PROMPT + common + "\nImplement this task and complete host validation.\n"
    else:
        preparation = common + """
Continue this task with the selected coordinator from the handoff and current source/evidence.
Start by investigating the previous VM validation error, when present, using the
live diagnosis and repair loop above when its cause is not established. Review
unstaged code (including new files) and retained failure evidence, apply the
repository failure contract and repair authorized defects. For interrupted or
blocked work, recheck the operation or prerequisite and owned test cleanup first.
Finish remaining implementation or repairs and complete host validation before
starting live acceptance in this same session.
"""
        if state['phase'] == 'recover':
            preparation += f"\nLast operation evidence: {state.get('recovery_run', 'see handoff')}/output and prompt.txt.\n"
        preparation += f"\nPrevious session's handoff:\n{state['handoff']}\n"
    return preparation + """
Use this same validation and handoff boundary in every session, including recovery.
After host checks pass, run this task's live VM acceptance, including required
regressions, under the plan. Wait for validation and owned cleanup to finish.
If live acceptance fails, preserve failure evidence and return ready_for_vm with
host_validated true, live_result failed and a fresh handoff for the next coordinator
selected by the launcher.
Leave investigation and repairs of this new failure to the next session; do not
repair it, retry live acceptance or advance the pointer in this session.
Do not end a normal session with only host validation: finish live VM validation
with a passed or failed result, except for the investigating continuation above
when the previous failure still needs useful live diagnosis. If a prerequisite still prevents validation after
authorized repair and requires developer action, return blocked with the actual
live_result and the specific external action needed; do not claim a VM attempt.
After all acceptance and cleanup pass, complete the plan's close-out and return
task_complete with live_result passed and the next-task handoff. Leave the next
task's implementation to a fresh session. Task 192 may instead return
task_complete with live_result not_run after its host-only acceptance and close-out.
"""


def optimization_prompt(state):
    batch = state['optimization']['pending']
    return f"""You are the GPT-6.1-Sol High coordinator and implementer for this session.
Follow AGENTS.md and the ownership map in docs/TestAutomation/README.md.
Use GPT-6.1 Sol for implementation and advice. The shared mandatory backend_reviewer
is the sole Astra exception, only for core backend changes.
Ignore conflicting model recommendations in repository instructions or older handoffs.
This is the mandatory optimization after three completed tasks, not a queue task.

## Scope
Tasks {batch[0]} to {batch[-1]} in {QUEUE}; exact completed IDs: {', '.join(batch)}.
Do not implement or close another task, change queue status/order or advance its pointer.
Optimize the current delivered code. Completed tasks stay complete: do not collect
proof, repair old report links or repeat their validation. Refactoring changes
own only their affected checks; unchanged code needs no new test run.

## Ask 1
Analyze lessons and successful experiences from this batch that can make future
tasks easier, increase first-time pass rate, reduce trial-and-error sessions and
completion time. Read current implementations and delivered queue scope.
Trust completed tasks; do not collect or revalidate their reports. Add useful guidance into
its owning instructions or mandates; search existing guidance and avoid duplicates.
Do not create a lessons archive or infer lessons unsupported by evidence.

## Ask 2
Audit the E2E case code delivered or affected by this batch, including its ready
case bindings in tests/e2e/scenarios.json. Each ready case must be a composition
of reusable building blocks, harness and libraries with finite case data, ordering
and assertions. Refactor one-off mechanics into the existing shared owners to
maximize reuse across cases. Preserve customer assertions, provider qualifications,
ownership, guards and acceptance; do not broaden this batch to unrelated cases.
Use tests/support/README.md and the shared task contract in
docs/TestAutomation/E2E-Execution-Contracts.md. Read applicable mandates before edits.

## Ask 3
Review code delivered or affected by each task in this batch for mess accumulated
across progressive sessions of the same task. Clean up redundant or obsolete code,
temporary workarounds and inconsistent structure left by successive attempts.
Keep the cleanup within the batch's affected code and preserve behavior,
customer assertions, provider qualifications, ownership, guards and acceptance.

Complete affected regressions and resource review. Runtime/provider changes need
their required live qualification; documentation-only changes need no live run.
Validate changed Markdown through tools/read-only links. Wait for owned cleanup.

The launcher owns staging and commits the validated fix as
"TA: Refactored task {batch[0]} to {batch[-1]}". Do not commit, push, publish or
invoke write-e2e/fix-tests. Preserve unrelated staged and unstaged work. Read
current source; do not inspect prior Codex sessions, memories or transcripts.
No ordinary delegation; the shared mandatory backend_reviewer remains required for
core backend changes. Run tests through tools/run-tests and preserve ONPC_WORKFLOW_DIRECTORY.
{LIVE_DIAGNOSIS_INSTRUCTIONS}
This optimization is resumable; use its checkpoint to finish interrupted operations
and owned cleanup. Missing historical reports require no work. Missing authority or a
required behavior decision returns blocked with a concrete question.

Return the existing structured result with task_id {state['task_id']}.
Use task_complete only when all three asks, affected validation and cleanup are done,
host_validated true, live_result passed or not_run as appropriate, progress outcome
not_applicable, and explicit optimization-owned stage_paths (deletions included).
After failed live validation, completion requires a subsequent clean live pass;
not_run cannot clear that failure, including after blockers or diagnostic rounds.
No changes or lessons is a valid audited outcome; summarize the findings briefly.
A failed live validation returns ready_for_vm with host_validated true and a
failed live_result. After that failure, useful unresolved live diagnosis may return
investigating as above; reasoning with no useful next step returns stalled.
Keep summary under 600 characters and handoff under 16000; carry only findings,
decisions, remaining work and relevant check selectors across sessions.
{BLOCKER_INSTRUCTIONS}

Previous optimization handoff:
{state['handoff']}
Last formal live acceptance: {json.dumps(acceptance_evidence(state), ensure_ascii=False)}
User answer: {json.dumps(state.get('user_answer'), ensure_ascii=False)}
Recovery evidence: {state.get('recovery_run', 'current workflow directory')}
"""


def optimization_due(state):
    return len(state.get('optimization', {}).get('pending', [])) >= OPTIMIZATION_INTERVAL


def record_completion(state):
    """Count accepted, committed tasks exactly once across close-out recovery."""
    if state.get('optimization_session') or state.get('completion_recorded'):
        return
    ledger = state.setdefault('optimization', {'pending': [], 'last_checkpoint': None})
    if len(ledger['pending']) >= OPTIMIZATION_INTERVAL:
        raise ValueError('optimization is due before another task can complete')
    ledger['pending'].append(state['task_id'])
    state['completion_recorded'] = True


def start_optimization(state):
    batch = state['optimization']['pending']
    if len(batch) != OPTIMIZATION_INTERVAL:
        raise ValueError('optimization checkpoint must contain exactly three completed tasks')
    selected = fresh_state(batch[-1])
    selected.update(optimization=state['optimization'], optimization_session=True,
                    phase='optimize', commit_required=True,
                    handoff='Analyze this completed batch and audit its reusable E2E composition.')
    if state.get('suspended_tasks'):
        selected['suspended_tasks'] = state['suspended_tasks']
    return selected


def acceptance_evidence(state):
    """Keep live evidence independent of promotion accounting and session status."""
    if 'acceptance' in state:
        return state['acceptance']
    # Migrate retained checkpoints without inventing checkpoint details. Blockers
    # did not spend failed_attempts, but older progress may still prove a failure.
    progress = state.get('progress')
    if ((progress or {}).get('failure_checkpoint')
            or state.get('failed_attempts', state.get('live_attempts', 0))):
        return {'live_result': 'failed', 'progress': progress}
    return None


def validate_progress(state, result):
    progress = result.get('progress')
    if progress is None and 'progress' not in result and result['status'] not in ('stalled', 'investigating'):
        # Retained results from an older launcher still use all acceptance guards.
        return None
    if (not isinstance(progress, dict)
            or set(progress) != {'failure_checkpoint', 'furthest_checkpoint', 'repair_outcome'}
            or any(not isinstance(progress[key], str) or len(progress[key]) > 240
                   for key in ('failure_checkpoint', 'furthest_checkpoint'))):
        raise ValueError('invalid escalation progress')
    outcome = progress['repair_outcome']
    allowed = ({'stalled'} if result['status'] == 'stalled' else
               {'diagnostic'} if result['status'] == 'investigating' else
               {'advanced', 'diagnostic', 'failed_repair'} if result['status'] == 'ready_for_vm'
               else {'not_applicable'})
    if (not isinstance(outcome, str) or outcome not in allowed
            or bool(progress['failure_checkpoint'].strip()) != (result['live_result'] == 'failed')):
        raise ValueError('escalation progress does not match validation outcome')
    if outcome == 'failed_repair':
        acceptance = acceptance_evidence(state) or {}
        previous = acceptance.get('progress') or {}
        if (acceptance.get('live_result') != 'failed' or not previous.get('failure_checkpoint')
                or progress['failure_checkpoint'] != previous['failure_checkpoint']
                or progress['furthest_checkpoint'] != previous['furthest_checkpoint']):
            raise ValueError('failed repair must retain the same failure and verified checkpoint')
    return progress


def validate_checks(state, result):
    """Check reported outcomes and target scope without reading report files."""
    checks = result.get('checks')
    if checks is None:
        return
    if not isinstance(checks, list) or not checks:
        raise ValueError('reported E2E checks must be nonempty')
    binding = state.get('vm')
    targets = binding.get('vms', []) if isinstance(binding, dict) else [binding] if binding else []
    for check in checks:
        if (not isinstance(check, dict) or not {'kind', 'target', 'result'}.issubset(check)
                or set(check) - {'kind', 'target', 'result', 'evidence'}
                or check['kind'] not in ('host', 'installed')
                or check['result'] not in ('passed', 'failed', 'not_run')
                or not isinstance(check['target'], str)
                or 'evidence' in check and not isinstance(check['evidence'], str)
                or check['kind'] == 'host' and check['target']
                or check['kind'] == 'installed' and (not check['target'] or
                    targets and check['target'] not in targets)):
            raise ValueError('invalid E2E check or target')
    if (result['host_validated'] and not any(check['kind'] == 'host' and
            check['result'] == 'passed' for check in checks)
            or any(check['kind'] == 'host' and check['result'] != 'passed'
                   for check in checks) and result['host_validated']):
        raise ValueError('reported checks do not match host validation')
    installed = [check for check in checks if check['kind'] == 'installed']
    if (result['live_result'] != 'not_run' and not any(
            check['result'] == result['live_result'] for check in installed)
            or result['live_result'] == 'passed' and any(check['result'] != 'passed' for check in installed)
            or result['live_result'] == 'passed' and targets and
                set(check['target'] for check in installed) != set(targets)
            or result['live_result'] == 'not_run' and any(check['result'] != 'not_run' for check in installed)):
        raise ValueError('reported checks do not match the live result')
    return


def accept_result(root, state, result, before):
    if (not isinstance(result, dict) or result.get('task_id') != state['task_id']
            or result.get('status') not in ('ready_for_vm', 'investigating', 'task_complete', 'blocked', 'stalled')
            or result.get('live_result') not in ('not_run', 'failed', 'passed')
            or type(result.get('host_validated')) is not bool
            or not isinstance(result.get('stage_paths'), list)
            or any(not isinstance(path, str) or not path for path in result['stage_paths'])
            or any(not isinstance(result.get(key), str) or not result[key].strip()
                   for key in ('summary', 'handoff'))
            or len(result['summary']) > 600 or len(result['handoff']) > 16000):
        raise ValueError('agent returned an invalid or wrong-task handoff')
    blocker = result.get('blocker')
    if result['status'] == 'blocked':
        validate_blocker(blocker)
    elif blocker is not None:
        raise ValueError('only a blocked result may ask a question')
    validate_checks(state, result)
    progress = validate_progress(state, result)
    acceptance = acceptance_evidence(state)
    outstanding_failure = bool(acceptance and acceptance['live_result'] == 'failed')
    if result['status'] == 'investigating':
        if not outstanding_failure or result['live_result'] != 'not_run':
            raise ValueError('diagnostic continuation requires a prior failed acceptance and no new live result')
    if result['live_result'] != 'not_run':
        acceptance = {'live_result': result['live_result'], 'progress': progress}
        if result.get('checks') is not None:
            acceptance.update(checks=result['checks'], host_validated=result['host_validated'],
                              session=state.get('task_sessions', 0))
    current, after = queue_state(root)
    task = state['task_id']
    if state.get('optimization_session'):
        if list(after.items()) != list(before.items()):
            raise ValueError('optimization changed queue status or order')
        if result['status'] == 'task_complete' and (
                not result['host_validated'] or result['live_result'] == 'failed'
                or (outstanding_failure and result['live_result'] != 'passed')):
            raise ValueError('optimization completion lacks passing validation')
        if result['status'] != 'task_complete' and result['stage_paths']:
            raise ValueError('incomplete optimization requested staging')
        if result['status'] == 'ready_for_vm' and (
                not result['host_validated'] or result['live_result'] != 'failed'):
            raise ValueError('optimization handoff lacks matching live outcome')
        if result['status'] == 'stalled' and result['live_result'] == 'passed':
            raise ValueError('optimization stall cannot claim passing live acceptance')
        updated = dict(state, summary=result['summary'], handoff=result['handoff'],
                    in_flight=False, blocker=blocker, acceptance=acceptance,
                    progress=state.get('progress') if result['live_result'] == 'not_run' else progress,
                    diagnostic_progress=progress if result['status'] == 'investigating' else None,
                    diagnostic_continuation=result['status'] == 'investigating',
                    phase='complete' if result['status'] == 'task_complete' else
                          'blocked' if result['status'] == 'blocked' else 'optimize')
        return retain_diagnostic_state(updated, result)
    if any(after.get(key) != complete for key, complete in before.items() if key != task):
        raise ValueError('agent changed another task status; inspect the queue')
    status = result['status']
    if status != 'task_complete' and result['stage_paths']:
        raise ValueError('incomplete task requested staging')
    if status == 'task_complete':
        if (not after.get(task) or current == task or not result['host_validated']
                or (task != '192' and (state['phase'] not in ('implement', 'live', 'recover')
                                      or result['live_result'] != 'passed'))):
            raise ValueError('task completion lacks acceptance or queue close-out')
    elif current != task or after.get(task):
        if not (status == 'blocked' and result['live_result'] == 'not_run'
                and prerequisite_repair(root, state, before)):
            raise ValueError('incomplete task advanced the queue pointer')
    if status == 'ready_for_vm':
        if not result['host_validated'] or result['live_result'] != 'failed':
            raise ValueError('VM handoff lacks host validation or a matching live outcome')
    if status == 'stalled' and result['live_result'] == 'passed':
        raise ValueError('reasoning stall cannot claim passing live acceptance')
    updated = dict(state, summary=result['summary'], handoff=result['handoff'], in_flight=False,
                   acceptance=acceptance)
    updated['model_tier'] = model_tier(state)
    updated['failed_attempts'] = state.get('failed_attempts', state.get('live_attempts', 0))
    updated['diagnostic_continuation'] = status == 'investigating'
    if status == 'investigating':
        # Retain formal failure/checkpoint evidence for later same-checkpoint
        # failed-repair promotion; diagnostic probes are not acceptance attempts.
        updated['diagnostic_progress'] = progress
    else:
        updated.pop('diagnostic_progress', None)
    if status in ('ready_for_vm', 'stalled'):
        if result['live_result'] == 'failed':
            updated['failed_attempts'] += 1
        if progress is not None:
            updated['progress'] = progress
        if status == 'stalled' or (progress and progress['repair_outcome'] == 'failed_repair'):
            updated['model_tier'] = min(model_tier(state) + 1, len(MODEL_TIERS) - 1)
        updated['model_tier'] = model_tier(updated)
    updated.pop('completion_recovery', None)
    updated.pop('blocker_id', None)
    updated['blocker'] = blocker
    if state['phase'] in ('implement', 'live', 'recover') and result['live_result'] != 'not_run':
        updated['live_attempts'] += 1
    updated['phase'] = ('complete' if status == 'task_complete' else
                        'live' if status in ('ready_for_vm', 'investigating') else
                        'recover' if status == 'stalled' else 'blocked')
    if current != task and status == 'blocked':
        return defer_to_prerequisite(root, retain_diagnostic_state(updated, result))
    return retain_diagnostic_state(updated, result)


def retain_diagnostic_state(state, result):
    if result['status'] == 'investigating' and result.get('checks') is not None:
        state['diagnostic_evidence'] = dict(checks=result['checks'], live_result='not_run',
            host_validated=result['host_validated'], session=state.get('task_sessions', 0))
    elif result['status'] != 'investigating':
        state.pop('diagnostic_evidence', None)
    return state


def wait_for_answer(run, state, progress_key, *, on_poll=lambda: None):
    """The detached owner waits; terminals may come and go without answering."""
    from launcher_progress import read_progress
    blocker = state.get('blocker') or {
        'explanation': state['summary'],
        'question': 'How should we unblock this task?',
        'options': ['Recheck the blocker and resolve work already authorized.',
                    'Inspect the evidence and explain the decision needed before making changes.']}
    state.setdefault('blocker_id', uuid.uuid4().hex)
    steps = read_progress(run)
    heading = steps[-1]['lines'][0] if steps else f"Task {state['task_id']}"
    launcher.atomic(run / 'chat-state.json', {'session': state.get('total_sessions'),
                    'task_session': state['task_sessions'], 'task_id': state['task_id'], 'status': 'blocked'})
    answer = wait_for_developer(
        run, blocker, state['blocker_id'], progress_key, label='write-e2e', heading=heading,
        on_wait=lambda: save_handoff(run, state, 'waiting for your answer', display=False),
        on_poll=on_poll)
    if answer is None:
        return False
    state.update(phase='recover', recovery_run=str(run), user_answer=answer)
    state.pop('blocker_id', None)
    state.pop('blocker', None)
    launcher.atomic(run / 'checkpoint.json', state)
    print('Answer received. Continuing this task.', flush=True)
    return True


def stage_task(root, paths, *, require_closeout=True):
    from launcher_git import stage_task as stage
    return stage(root, paths, required_paths=(PLAN, QUEUE) if require_closeout else ())


def stage_completion(root, state, result):
    current = worktree_snapshot(root)
    changed = [path for path in state['stage_candidates']
               if path in current and current[path] != state.get('stage_baseline', {}).get(path)]
    paths = [*result['stage_paths'], *changed]
    overlap = set(paths).intersection(state.get('protected_staged', []))
    if state.get('commit_required') and overlap:
        raise ValueError('completion overlaps pre-existing staged work: ' + ', '.join(sorted(overlap)))
    return stage_task(root, paths,
                      require_closeout=not state.get('optimization_session'))


def finish_completion(root, run, state, result, updated):
    with closeout_lock(root, run, state):
        return _finish_completion(root, run, state, result, updated)


def _finish_completion(root, run, state, result, updated):
    validate_checks(state, result)
    if state.get('commit_intent'):
        paths = state['commit_intent']['paths']
    else:
        paths = stage_completion(root, state, result)
    if state.get('commit_required'):
        batch = state.get('optimization', {}).get('pending', [])
        message = (f'TA: Refactored task {batch[0]} to {batch[-1]}'
                   if state.get('optimization_session') else f"TA: Completed task {state['task_id']}")
        commit = commit_push_propagate(root, run, state, paths, message, git=git_output)
        if state.get('optimization_session'):
            updated['optimization'] = {'pending': [], 'last_checkpoint': {
                'tasks': list(state['optimization']['pending']), 'commit': commit}}
            updated.pop('optimization_session', None)
        else:
            record_completion(updated)
    updated.pop('commit_intent', None)
    updated.pop('pending_completion', None)
    updated.pop('worktree_before', None)
    updated.pop('worktree_propagation', None)
    return updated


def recover_completion(root, run, state, *, destination=None):
    """Retry accepted staging, or reconcile missing completion in a fresh session."""
    current, after = queue_state(root)
    if state.get('optimization_session'):
        result = state.get('pending_completion')
        if result is None:
            return state
        updated = accept_result(root, state, result, state['queue_before'])
        return finish_completion(root, destination or run, state, result, updated)
    if (not state.get('in_flight') or current == state['task_id']
            or not after.get(state['task_id']) or not state.get('queue_before')):
        return state
    result = state.get('pending_completion')
    if result is None:
        # Older launchers kept the result but failed before checkpointing it.
        path = run / 'agent-result.json'
        try:
            result = json.loads(path.read_text()) if path.is_file() else None
        except json.JSONDecodeError:
            result = None
    updated = None
    if isinstance(result, dict) and result.get('status') == 'task_complete':
        try:
            updated = accept_result(root, state, result, state['queue_before'])
        except ValueError:
            # An unaccepted legacy response is evidence for the coordinator,
            # never authority to stage. A checkpointed accepted result retains
            # its stricter staging-only recovery and must pass every guard.
            if state.get('pending_completion') is not None:
                raise
    if updated is None:
        before = validate_completion_queue(state, after)
        print(f"write-e2e: automatically reconciling interrupted task {state['task_id']} "
              'before starting the next task.', flush=True)
        return dict(state, phase='recover', in_flight=False, completion_recovery=True,
                    recovery_run=str(run), queue_before=before)
    updated = finish_completion(root, destination or run, state, result, updated)
    print(f"write-e2e: recovered completed task {state['task_id']}; close-out passed.", flush=True)
    return updated


def validate_completion_queue(state, after):
    """Preserve old task order/status and adopt newly queued unchecked work."""
    before = state.get('queue_before', {})
    task = state['task_id']
    expected = dict(before)
    expected[task] = True
    retained = {key: complete for key, complete in after.items() if key in before}
    if (before.get(task) is not False or retained != expected
            or list(retained) != list(before)
            or any(complete for key, complete in after.items() if key not in before)):
        raise ValueError('interrupted task changed the queue; inspect the saved handoff')
    # Include additions in the recovery baseline so accept_result also guards
    # their status. Updating this new state never rewrites the saved checkpoint.
    return dict(after, **{task: False})


def save_handoff(run, state, reason, *, display=True):
    prompt = state['handoff'] + result_recovery_instructions(state.get('result_recovery'))
    if state.get('pending_completion'):
        prompt = (f"Task {state['task_id']} passed acceptance and queue close-out; Git close-out remains. "
                  "Staging, its completion commit and/or git push remain. "
                  "Restart tools/write-e2e to retry close-out from the retained result before "
                  "starting the next task. Do not rerun acceptance.\n" + prompt)
    elif state['in_flight']:
        prompt = (
            f"Recover interrupted task {state['task_id']}. Inspect {run / 'output'} and "
            f"{run / 'prompt.txt'}; verify retained test results and owned cleanup "
            "before retrying. Do not assume live acceptance passed or advance the "
            "task. Continue with the launcher-selected coordinator. Last safe handoff:\n" + prompt)
    if state['phase'] != 'complete' and not state.get('pending_completion'):
        model, effort = session_model(state)
        prompt = f'Next coordinator and implementer: {model} {effort}.\n\n' + prompt
    text = f"Task {state['task_id'] or 'none'}: {reason}. {state['summary']}\n\nNext session prompt:\n{prompt}\n"
    (run / 'handoff.txt').write_text(text, encoding='utf-8')
    launcher.atomic(run / 'checkpoint.json', state)
    if display:
        from launcher_render import AgentRenderer
        if state['phase'] == 'blocked':
            # The decision was already shown when the workflow paused. Keep the
            # engineering continuation in the file, including on stop/cancel.
            text = f"Task {state['task_id']} is paused. Run tools/write-e2e to answer and continue."
        AgentRenderer(sys.stdout).message(text)
        sys.stdout.flush()


def show_completion(task, task_sessions, duration):
    from launcher_render import AgentRenderer
    from rich.text import Text
    console = AgentRenderer(sys.stdout).console
    console.rule(style='dim')
    console.print(Text(f'Task {task} complete.', style='bold green'))
    print(f'- Took {task_sessions} sessions.\n'
          f'- Duration: {format_duration(duration)}', flush=True)
    sys.stdout.flush()


def task_session_limit_reached(state):
    return (state['phase'] != 'complete'
            and state.get('task_sessions', 0) >= state.get('task_session_limit', MAX_TASK_SESSIONS))


def show_session_limit(state):
    from launcher_render import AgentRenderer
    from rich.text import Text
    message = (f"Task {state['task_id']} is not complete in {state['task_sessions']} sessions. "
               'Launcher exited early.')
    AgentRenderer(sys.stdout).console.print(Text(message, style='bold red'), soft_wrap=True)
    sys.stdout.flush()


def execute(root, run, owner, phase, live_attempts=0):
    (run / 'agent-result.json').write_text('')
    with launcher.lock(run / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        (run / 'nested-closed').unlink(missing_ok=True)
        launcher.atomic(run / 'nested.json', [])
    command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
               '--supervise', str(root), str(run), str(owner), phase, str(live_attempts)]
    with subprocess.Popen(command, cwd=root, env=launcher.environment(),
                          stdin=subprocess.PIPE, start_new_session=True,
                          pass_fds=(owner, *launcher.scratch_descriptors())) as child:
        status = child.wait()
    sys.stdout.flush()
    launcher.compact_log(run / 'output', writer_fd=1)
    if (run / 'cancel').exists():
        raise launcher.Stopped()
    if status:
        raise ValueError(f'Codex session exited with status {status}; see retained output')
    return read_session_result(run)


def task_info_instructions(run, task):
    from launcher_chat import task_info_instructions as instructions
    return instructions(run, task) + 'Describe the task in parent/child scenario language.\n'


def worker(root, run, owner, tasks, state_json):
    from launcher_progress import publish_progress, read_progress
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def cancel(*_):
        (run / 'cancel').touch(mode=0o600)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)
    # on_start saves recovered task state after allocation and before spawn.
    # Its checkpoint can therefore be newer than the prepared argv.
    checkpoint = run / 'checkpoint.json'
    state = json.loads(checkpoint.read_text() if checkpoint.exists() else state_json)
    state['commit_required'] = True
    total = state.get('total_sessions', state.get('task_sessions', 0))
    count, completed, status, reason = 0, 0, 0, 'task limit reached'
    completions = []
    retained_runtime = state.pop('reload_runtime', None)
    if retained_runtime is not None:
        count, completed = retained_runtime['sessions'], retained_runtime['completed']
        completions = retained_runtime['completions']
    budget = TaskBudget(run)
    reload_request = ReloadRequest(run)
    reloading = False
    final_replayed_stall = False

    def compact_completions():
        for task_id, task_sessions, duration, keys, heading in completions:
            publish_completion(run, task_id, heading, duration, keys)

    try:
        if (run / 'cancel').exists():
            raise launcher.Stopped()
        if state.get('source_changed_result') is not None:
            # The previous controller could not load changed validation code.
            # Replay its exact closed response under this fresh process without
            # spending another session or changing the acceptance attempt.
            result = state['source_changed_result']
            try:
                updated = validate_session_result(result, lambda result: accept_result(
                    root, state, result, state['queue_before']))
            except SessionResultRejected as error:
                state.pop('source_changed_result')
                state.update(phase='optimize' if state.get('optimization_session') else 'recover',
                             in_flight=False)
                retain_result_rejection(run, error, label='write-e2e', checkpoint=state)
            else:
                final_replayed_stall = (not state.get('optimization_session')
                    and result['status'] == 'stalled'
                    and model_tier(state) == len(MODEL_TIERS) - 1)
                if updated['phase'] == 'complete':
                    state.update(pending_completion=result)
                    launcher.atomic(run / 'checkpoint.json', state)
                    updated = finish_completion(root, run, state, result, updated)
                    if not state.get('optimization_session'):
                        completed += 1
                        budget.complete()
                state = updated
                state.pop('source_changed_result', None)
                state.pop('result_recovery', None)
                state.pop('worktree_before', None)
                if final_replayed_stall:
                    status, reason = 1, 'reasoning stalled at GPT-6.1 Sol Max; inspect the retained evidence'
                launcher.atomic(run / 'checkpoint.json', state)
        if state.get('closeout_recovery_run'):
            previous = Path(state.pop('closeout_recovery_run'))
            state = recover_completion(root, previous, state, destination=run)
            if state['phase'] == 'complete' and not optimization_due(state):
                state = select_task_state(queue_state(root)[0], state)
                total = state.get('task_sessions', 0)
            state['commit_required'] = True
            launcher.atomic(run / 'checkpoint.json', state)
        while not final_replayed_stall:
            if (run / 'cancel').exists():
                raise launcher.Stopped()
            if state['phase'] == 'complete' and optimization_due(state):
                state = start_optimization(state)
                launcher.atomic(run / 'checkpoint.json', state)
            if (run / 'stop').exists():
                reason = 'stopped at a session boundary'
                break
            reload_request.check()
            if state['phase'] == 'blocked':
                if not wait_for_answer(run, state, str(count), on_poll=reload_request.check):
                    reason = 'paused at your request'
                    break
                # An explicit answer authorizes a recovery session even when
                # the automatic-work budget ended at the blocker. Waiting itself
                # consumes no model session and never renews a budget.
                state['task_session_limit'] = max(state.get('task_session_limit', MAX_TASK_SESSIONS),
                                                  state['task_sessions'] + 1)
                launcher.atomic(run / 'checkpoint.json', state)
                reload_request.check()
            if task_session_limit_reached(state):
                status, reason = 1, 'task session limit reached'
                budget.close()
                break
            if not budget.admit(exempt=bool(state.get('optimization_session'))):
                reason = 'task limit reached'
                break
            tasks = budget.read()['tasks']
            if (run / 'cancel').exists():
                raise launcher.Stopped()
            if (run / 'stop').exists():
                reason = 'stopped at a session boundary'
                break
            if state.get('result_recovery'):
                # A rejected response may have left a partial queue edit. Keep
                # the original baseline until the coordinator satisfies it.
                task, before = state['task_id'], state['queue_before']
            else:
                task, before = queue_state(root)
            if state.get('optimization_session'):
                task = state['task_id']
            elif state.get('completion_recovery') and not state.get('result_recovery'):
                before = validate_completion_queue(state, before)
                # The pointer already names the next task. Keep the interrupted
                # task and its original status baseline until acceptance is proven.
                task = state['task_id']
            remaining = sum(not done for done in before.values())
            budget.update(lambda value: value.update(remaining=remaining + value['completed']))
            if task is None:
                state = dict(state, task_id=None, summary='All active queue tasks are complete.',
                             handoff='No active E2E task remains. Do not select deferred tasks.', phase='complete')
                reason = 'queue complete'
                break
            if state['phase'] == 'complete':
                state = select_task_state(task, state)
                state['commit_required'] = True
                compact_completions()
                if task_session_limit_reached(state):
                    status, reason = 1, 'task session limit reached'
                    break
            if task != state['task_id']:
                raise ValueError('active task changed outside the workflow; inspect the checkpoint')
            count += 1
            total += 1
            state['total_sessions'] = total
            state.setdefault('started_at', time.time())
            state['task_sessions'] = state.get('task_sessions', 0) + 1
            state.setdefault('progress_keys', []).append(str(count))
            prompt = session_prompt(state)
            prompt += result_recovery_instructions(state.get('result_recovery'))
            prompt += task_info_instructions(run, state['task_id'])
            (run / 'prompt.txt').write_text(prompt, encoding='utf-8')
            state.setdefault('stage_baseline', worktree_snapshot(root))
            if 'protected_staged' not in state:
                state['protected_staged'] = list(filter(None, git_output(
                    root, 'diff', '--cached', '--name-only', '-z').stdout.split('\0')))
            state['worktree_before'] = worktree_snapshot(root)
            state['queue_before'] = before
            state['in_flight'] = True
            launcher.atomic(run / 'checkpoint.json', state)
            launcher.atomic(run / 'progress.json', {'session': count,
                                                   'task_id': task, 'phase': state['phase']})
            progress_lines = session_progress(root, state, total)
            publish_progress(run, str(count), progress_lines)
            model, effort = session_model(state)
            print(f"\nwrite-e2e: session {count}; "
                  f"task {task}; {model} {effort}", flush=True)
            try:
                try:
                    result = execute(root, run, owner, state['phase'], state['live_attempts'])
                finally:
                    candidates = set(state['stage_candidates'])
                    candidates.update(session_changes(root, state['worktree_before']))
                    state['stage_candidates'] = sorted(candidates)
                    launcher.atomic(run / 'checkpoint.json', state)
                    launcher.finish_nested(root, run)
                if reload_request.pending():
                    state['source_changed_result'] = result
                    launcher.atomic(run / 'checkpoint.json', state)
                    raise ReloadRequested()
                updated = validate_session_result(result, lambda result: accept_result(root, state, result, before))
            except SessionResultRejected as error:
                launcher.finish_nested(root, run)
                state.update(phase='optimize' if state.get('optimization_session') else 'recover',
                             in_flight=False)
                retain_result_rejection(run, error, label='write-e2e', checkpoint=state)
                reload_request.check()
                continue
            updated.pop('result_recovery', None)
            optimizing = bool(state.get('optimization_session'))
            final_stall = (not optimizing and result['status'] == 'stalled'
                           and model_tier(state) == len(MODEL_TIERS) - 1)
            if updated['phase'] == 'complete':
                state.update(pending_completion=result, summary=result['summary'], handoff=result['handoff'])
                launcher.atomic(run / 'checkpoint.json', state)
                updated = finish_completion(root, run, state, result, updated)
                if not optimizing:
                    completed += 1
                    budget.complete()
            state = updated
            state.pop('worktree_before', None)
            if state['phase'] == 'complete':
                state['completed_at'] = time.time()
            launcher.atomic(run / 'checkpoint.json', state)
            if final_stall:
                status, reason = 1, 'reasoning stalled at GPT-6.1 Sol Max; inspect the retained evidence'
                break
            if state['phase'] == 'complete' and optimizing:
                batch = state['optimization']['last_checkpoint']['tasks']
                publish_completion(run, f'optimization-{batch[0]}-{batch[-1]}',
                                   progress_lines[0],
                                   state['completed_at'] - state['started_at'],
                                   state['progress_keys'])
            elif state['phase'] == 'complete':
                keys = state['progress_keys']
                completions.append((task, state['task_sessions'],
                                    state['completed_at'] - state['started_at'], keys, progress_lines[0]))
                compact_completions()
        if (run / 'stop').exists():
            reason = 'stopped at a session boundary'
    except ReloadRequested:
        reloading, reason = True, 'manual reload requested; continuing the retained boundary'
    except launcher.Stopped:
        status, reason = 130, 'cancelled after owned cleanup'
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        status, reason = 1, str(error)
    finally:
        if reloading:
            try:
                launcher.finish_nested(root, run)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                reloading, status, reason = False, 1, f'owned cleanup failed: {error}'
            if (run / 'cancel').exists():
                reloading, status, reason = False, 130, 'cancelled after owned cleanup'
            elif (run / 'stop').exists():
                reloading, reason = False, 'stopped at a session boundary'
        if reloading:
            state['reload_runtime'] = dict(sessions=count, completed=completed, completions=completions)
            save_handoff(run, state, reason, display=False)
            try:
                replace_interpreter(['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                    '--worker', str(root), str(run), str(owner), json.dumps(tasks), '{}'],
                    (owner, *launcher.scratch_descriptors()))
            except OSError as error:
                status, reason = 1, f'controller reload failed: {error}; resume the retained run'
        try:
            launcher.finish_shutdown(root, run)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            status, reason = 1, f'owned cleanup failed: {error}'
        previous = read_progress(run)
        if previous and not previous[-1].get('replaces'):
            lines = previous[-1]['lines']
            outcome = ('Stopped' if status == 130 else 'Blocked' if status else
                       'Complete' if state['phase'] == 'complete' else reason)
            lines[-1] += ' — ' + outcome
            publish_progress(run, previous[-1]['key'], lines)
        for task, task_sessions, duration, _, _ in completions:
            show_completion(task, task_sessions, duration)
        save_handoff(run, state, reason,
                     display=not (status == 0 and completed and state['phase'] == 'complete'))
        if task_session_limit_reached(state) and state['phase'] != 'blocked':
            show_session_limit(state)
        if completions:
            from launcher_render import AgentRenderer
            print(f'- Total launcher sessions: {total}', flush=True)
            AgentRenderer(sys.stdout).console.rule(style='dim')
            sys.stdout.flush()
        launcher.atomic(run / 'result.json', {'status': status, 'sessions': count,
                                             'tasks': completed})
        os.close(owner)
    return status


def initial_state(root, directory, *, destination=None, defer_closeout=False):
    previous = launcher.current_run(directory)
    if previous and (previous / 'checkpoint.json').exists():
        state = json.loads((previous / 'checkpoint.json').read_text())
        # Progress keys name frames in one launcher, unlike cumulative task sessions.
        for saved in [state, *state.get('suspended_tasks', {}).values()]:
            saved.pop('progress_keys', None)
            for key in ('evidence_turns', 'evidence_consumers', 'diagnostic_evidence'):
                saved.pop(key, None)
        if state.get('result_recovery'):
            used = state.get('task_sessions', 0)
            return dict(state, recovery_run=str(previous), total_sessions=used,
                        task_session_limit=used + MAX_TASK_SESSIONS)
        if state.get('source_changed_result') is not None:
            used = state.get('task_sessions', 0)
            return dict(state, recovery_run=str(previous), total_sessions=used,
                        task_session_limit=used + MAX_TASK_SESSIONS)
        task, _ = queue_state(root)
        resumed = resume_after_exclusion(root, state, previous)
        if resumed is not None:
            used = resumed.get('task_sessions', 0)
            return dict(resumed, total_sessions=used,
                        task_session_limit=used + MAX_TASK_SESSIONS)
        if defer_closeout and (state.get('closeout_recovery_run') or state.get('pending_completion')
                or (state.get('in_flight') and queue_state(root)[1].get(state['task_id']))):
            state.setdefault('closeout_recovery_run', str(previous))
            used = state.get('task_sessions', 0)
            return dict(state, total_sessions=used,
                        task_session_limit=used + MAX_TASK_SESSIONS)
        state = recover_completion(root, previous, state, destination=destination)
        if state.get('optimization_session'):
            if state.get('in_flight') and state.get('worktree_before') is not None:
                candidates = set(state.get('stage_candidates', []))
                candidates.update(session_changes(root, state['worktree_before']))
                state['stage_candidates'] = sorted(candidates)
            question_path = previous / 'question.json'
            if state.get('phase') == 'blocked' and question_path.exists():
                question = json.loads(question_path.read_text())
                if question['id'] == state.get('blocker_id') and question.get('answer') is not None:
                    state.update(phase='optimize', recovery_run=str(previous),
                                 user_answer={'question': question['question'], 'answer': question['answer']})
                    state.pop('blocker_id', None)
                    state.pop('blocker', None)
            if state.get('in_flight'):
                state.update(phase='optimize', in_flight=False, recovery_run=str(previous))
            used = state.get('task_sessions', 0)
            return dict(state, total_sessions=used,
                        task_session_limit=used + MAX_TASK_SESSIONS)
        if state['phase'] == 'complete' and optimization_due(state):
            return start_optimization(state)
        # Completion reconciliation uses recorded candidates and the recovering
        # agent's explicit owned paths. A scan after the old run ended would
        # wrongly attribute later developer work to the interrupted task.
        if state.get('in_flight') and state.get('worktree_before') is not None:
            candidates = set(state.get('stage_candidates', []))
            candidates.update(session_changes(root, state['worktree_before']))
            state['stage_candidates'] = sorted(candidates)
        if state.get('phase') == 'complete' and task in state.get('suspended_tasks', {}):
            state = select_task_state(task, state)
        elif (state.get('in_flight') and state.get('task_id') != task
              and prerequisite_repair(root, state, state.get('queue_before'))):
            state = defer_to_prerequisite(root, state, recovery_run=previous)
        if ((state.get('task_id') == task or state.get('completion_recovery'))
                and state.get('phase') != 'complete'):
            if state.get('task_id') == task:
                state.pop('completion_recovery', None)
            question_path = previous / 'question.json'
            if state.get('phase') == 'blocked' and question_path.exists():
                question = json.loads(question_path.read_text())
                if question['id'] == state.get('blocker_id') and question.get('answer') is not None:
                    # Preserve an answer submitted just before stop/worker death,
                    # even if the owner had not checkpointed its recovery yet.
                    state.update(phase='recover', recovery_run=str(previous),
                                 user_answer={'question': question['question'], 'answer': question['answer']},
                                 task_session_limit=max(state.get('task_session_limit', MAX_TASK_SESSIONS),
                                                        state.get('task_sessions', 0) + 1))
                    state.pop('blocker_id', None)
                    state.pop('blocker', None)
            if state.get('in_flight'):
                state = dict(state, phase='recover', in_flight=False,
                             recovery_run=str(previous))
            # Keep the task's cumulative numbering, but give this new owner
            # five sessions of its own before the per-task stop applies again.
            used = state.get('task_sessions', 0)
            return dict(state, total_sessions=used,
                        task_session_limit=used + MAX_TASK_SESSIONS)
        if state.get('in_flight'):
            raise ValueError(f'interrupted task changed the queue; inspect the handoff in {previous}')
        return select_task_state(task, state)
    return fresh_state(queue_state(root)[0])


def select(root, argv):
    from vm_selection import extract, check_binding, save_binding, execution_selection, execution_binding, BATCH, VARIABLE
    argv, configured = extract(argv, required=False)
    if '--stop' in argv and configured is None:
        os.environ.pop(BATCH, None)
        os.environ.pop(VARIABLE, None)
    elif not any(option in argv for option in ('--help', '-h')):
        execution_selection(configured.name if configured else None)
    binding = execution_binding()
    initial_limits = {}
    initial_checkpoint = {}
    initial_info = {}

    def parse(attaching=False):
        parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
        parser.add_argument('--vm', help='registered VM name or ID; omitted: configured enabled queue and concurrency')
        add_options(parser, stop_help='finish the current session and stop before the next')
        return parser.parse_args(argv)

    if any(option in argv for option in ('--help', '-h')):
        parse()

    def attach(run):
        check_binding(run, binding, stopping='--stop' in argv)
        args = parse(attaching=True)
        if args.tasks is None:
            return
        limit = TaskBudget(run).set_limit(args.tasks)
        try:
            remaining = sum(not done for done in queue_state(root)[1].values())
        except (OSError, ValueError):
            pass  # Partial coordinator edits must not prevent attachment.
        else:
            warn_remaining(limit, remaining + TaskBudget(run).read().get('completed', 0),
                           label='write-e2e')
        print(f"write-e2e: limits now tasks={limit if limit is not None else 'all'}", flush=True)

    def command(run, owner):
        args = parse()
        if args.tasks is None:
            args.tasks = 1
        state = initial_state(root, run.parent, defer_closeout=True)
        before = state['queue_before'] if state.get('result_recovery') else queue_state(root)[1]
        remaining = sum(not done for done in before.values())
        initial_limits.update(tasks=task_limit(args.tasks), started=0, completed=0, remaining=remaining)
        warn_remaining(task_limit(args.tasks), remaining, label='write-e2e')
        state['vm'] = binding
        previous = launcher.current_run(run.parent)
        if previous is not None and (previous / 'task-info.json').exists():
            info = json.loads((previous / 'task-info.json').read_text())
            initial_info.update(info)
        # Preflight transport/rendering only; do not spend a model session here.
        from launcher_render import AgentRenderer
        session_command(root, state)
        initial_checkpoint.update(state)
        return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), '--worker',
                str(root), str(run), str(owner), json.dumps(args.tasks), json.dumps(state)]

    def start(run):
        launcher.atomic(run / 'limits.json', initial_limits)
        launcher.atomic(run / 'checkpoint.json', initial_checkpoint)
        save_binding(run, binding)
        # Read before retention can expire the previous run; write only after
        # select() has safely allocated the new destination.
        if initial_info:
            launcher.atomic(run / 'task-info.json', initial_info)

    return launcher.select(root, 'write-e2e', command, stop='--stop' in argv, stop_marker='stop',
                           on_attach=attach, on_start=start,
                           **({'reload': True} if '--reload' in argv else {}))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1]
    run, interrupted = None, False

    def cancel(*_):
        nonlocal interrupted
        interrupted = True
        if run is not None:
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
        run, started = select(root, argv)
        if run is None:
            print('write-e2e: no active launcher.')
            return 0
        if interrupted:
            cancel()
        print(f"write-e2e: {'started' if started else 'attached to'} {run.name}; log: {run / 'output'}",
              flush=True)
        print('Closing the terminal detaches. Chat Ctrl+C interrupts; again while waiting exits. '
              '--stop waits for a session boundary.',
              flush=True)
        from launcher_view import plan_view
        return launcher.follow(run, label='write-e2e', view=plan_view(root, PLAN))
    except BrokenPipeError:
        return 0
    except (OSError, ValueError, ImportError) as error:
        print(f'write-e2e: {error}', file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGINT, previous)


if __name__ == '__main__':
    mode, root, run, owner, *options = sys.argv[1:]
    if mode == '--worker':
        sys.exit(worker(Path(root), Path(run), int(owner), json.loads(options[0]), options[1]))
    if mode == '--supervise':
        root, run = Path(root), Path(run)
        # Older workers omit the phase or attempt count. Their checkpoint still
        # carries the task's attempts and session identity.
        state = json.loads((run / 'checkpoint.json').read_text())
        phase = options[0] if options else 'recover'
        attempts = int(options[1]) if len(options) > 1 else state.get('live_attempts', 0)
        state = dict(state, phase=phase, live_attempts=attempts)
        command = session_command(root, state, run)
        model, effort = session_model(state)
        metadata = {'session': state.get('total_sessions', state['task_sessions']),
                    'task_id': state['task_id'], 'phase': phase, 'model': model,
                    'reasoning_effort': effort, 'service_tier': 'default'}
        command[-1:-1] = ['-c', 'shell_environment_policy.set.ONPC_WORKFLOW_DIRECTORY=' + json.dumps(str(run))]
        from vm_selection import selected, BATCH
        vm = selected()
        command[-1:-1] = ['-c', 'shell_environment_policy.set.ONPC_TEST_VM=' + json.dumps(vm.name)]
        if BATCH in os.environ:
            command[-1:-1] = ['-c', 'shell_environment_policy.set.' + BATCH + '=' + json.dumps(os.environ[BATCH])]
        sys.exit(launcher.supervise(root, run, int(owner), 'agent', command, nested=True,
                                    hide_task_completion=True,
                                    interactive=True,
                                    on_model=lambda active: metadata.update(model=active),
                                    on_usage=lambda usage: record_usage(run, metadata, usage)))
    raise SystemExit('private write-e2e worker entry point')
