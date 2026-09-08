Continue the next unfinished task in docs/Test-Automation.md. This is the dev
and host machine. This invocation is one slice of the unattended session loop
that the user started to finish all tasks in the authoritative master checklist.

The user authorizes implementation and verification of successive slices within
that plan and the existing guarded test-VM scope. Proceed with the exact model
and effort supplied by the supervisor. The per-session “Go ahead” and settings
confirmation are already given for this unattended run; do not pause for them.
Every session is pinned to `gpt-6-astra` / `high`; record these settings in the handoff.
This authorization does not override execution policy, an approval denial,
Polkit policy, VM ownership, cleanup guards or requirements for an actual user
decision outside the established scope. Never widen permissions to continue.

Follow AGENTS.md, docs/TestAutomation/Continuation.md, the relevant active task
handoff, the authoritative checklist and Implementation-Workflow.md. Inspect
current edits and preserve other work. Read only the relevant task/contracts
and source. Do not read previous Codex transcripts or the supervisor's event
history. The maintained documents carry the compact context between sessions.
Apply Implementation-Workflow.md#vm-availability-for-all-tasks to every task:
the operator cleared the historical VM/writer-pause hold for the whole backlog.
Earlier evidence and handoffs cannot reinstate it. At the next safe boundary,
proceed with dependency-ready guarded VM work; do not add local-only slices or
request another coordination confirmation because of that resolved hold.
Preserve this clearance in each handoff. Actual runner refusals still require
current evidence and scoped diagnosis under the existing guards.
Never read, search, diff, edit or include docs/Test-Automation-Slice-Summary.md
in context, including through broad repository reads. It is an operator-only,
append-only log. The supervisor appends your final summary without reading its
existing contents; it is not a handoff input. Exclude it from bulk searches and
diffs, and inspect only relevant source changes.

State the next bounded result, verification and actual settings, then implement
and verify one coherent slice. Apply the workflow's quality, context and attempt
limits. Finish current commands, evidence collection and guarded cleanup before
ending. A slice budget is a review point, not permission to kill an operation.
Do not start another Codex process, reset this chat, run the loop launcher,
change its control state, or continue into an unrelated next slice.

Mark a checklist task complete only when all its required deliverables and
acceptance checks pass. Do not delete checklist entries during the unattended
run. A failed test is work to diagnose within the plan, not evidence of success.
If a task is blocked, retain its blocker and select independent ready work as
the workflow permits. Return blocked only if no ready work can proceed without
outside input. Record any denied action and its reason in the active handoff;
do not retry the denied action through a different route or new session.

Before ending, update the task's active handoff and Continuation.md with the
result, reusable evidence, next action, pinned model/effort and cleanup
state. Keep the settings line in Continuation.md in this exact form, followed
by its reason:

    - Settings: **`gpt-6-astra` / `high`**, pinned by the slice launcher.

Do not log PII or secrets. Describe any blocker and required intervention in the
active task handoff. The final response must conform to the supplied schema:

- status: continue after a slice with remaining ready work; complete only when
  every authoritative checklist entry is accepted; blocked when outside input
  is necessary and no independent ready work remains.
- cleanup_complete: true only after all commands this session started have
  exited, results are collected, and their required cleanup is confirmed.
  If state is uncertain, save exact owned identities/recovery information in the
  task handoff and return false. Never infer cleanup from old evidence.
- made_progress: true for a verified change, completed required verification,
  or new discriminating evidence that advances the next action. Rewording the
  same handoff or repeating the same failed experiment is not progress.
- blocker: none unless blocked; otherwise approval, environment, decision,
  or no-ready-task.
- summary: a concise, self-contained report of this session, with these string
  fields: task (task ID and result being pursued), completed (actual work and
  findings), verification (checks, evidence and cleanup, including failures),
  next (the next session's concrete action, or required outside intervention),
  remaining_sessions and remaining_minutes (ranges for finishing the named
  current task after this slice), and estimate_basis (measured work, assumptions
  and uncertainty). Give both estimates explicitly; use "Unknown" when evidence
  is insufficient and explain why. If the named task is accepted, its remaining
  estimates are zero; identify any different next task in next. Do not guess a
  backlog-wide finish date or read the summary log to calculate estimates.
  Use redacted role labels, repository-relative paths and test IDs; exclude
  personal names, account identifiers, secrets and raw command transcripts.
  The supervisor supplies session numbering, completion time and duration from
  its own clock. Do not append the report yourself.

After saving this one slice's handoff, end the turn. The supervisor will verify
the result and start a new Codex session if work remains. When all tasks are
complete, record completion and stop without rerunning accepted suites.
