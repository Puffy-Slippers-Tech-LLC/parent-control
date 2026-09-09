Continue the next unfinished task in docs/Test-Automation.md. This is the dev
and host machine. This invocation is one slice of the unattended session loop
that the user started to finish all tasks in the authoritative master checklist.

The user authorizes implementation and verification of successive slices within
that plan and the existing guarded test-VM scope. Proceed with the exact model
and effort supplied by the supervisor. The per-session “Go ahead” and settings
confirmation are already given for this unattended run; do not pause for them.
Follow Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff:
quality first, weekly allowance second. Sol high is the settled-implementation
default; choose Astra high upfront for unresolved security, concurrency,
ownership, difficult diagnosis or broad correctness review. Lower settings need
a settled contract and adequate checks. There is no blanket model/effort pin;
historical pinned settings cannot override this policy. Processing is Standard.
This authorization does not override execution policy, an approval denial,
Polkit policy, VM ownership, cleanup guards or requirements for an actual user
decision outside the established scope. Never widen permissions to continue.

Follow AGENTS.md, docs/TestAutomation/Continuation.md, the relevant active task
handoff, the authoritative checklist and Implementation-Workflow.md. Inspect
current edits and preserve other work. Read only the relevant task/contracts
and source. Do not read previous Codex transcripts or the supervisor's event
history. The maintained documents carry the compact context between sessions.
Before investigating shared infrastructure, read the selected task's Reuse-Map.md
row and its relevant owning contract, regression and open-limitation links.
Apply Implementation-Workflow.md#reuse-established-tools-and-bound-harness-work:
identify the reused helper and only the missing capability or evidenced change
that warrants reopening a solution. Publish changed shared findings in the
owning contract and affected map links before handoff; check that their
qualification claims agree with retained evidence. Do not leave reusable
solutions only in the task handoff or operator summary.
Apply Implementation-Workflow.md#start-with-one-bounded-result at every safe
slice boundary: select the earliest ready unchecked task in checklist order.
Reconcile a later continuation pointer and recheck earlier deferrals before
another fallback slice. Record each bypassed entry's dependency/blocker evidence
and return condition in its handoff, linked from Continuation.md. Return to an
earlier task when it becomes ready; preserve later work in its own handoff.
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
limits. Keep progress and the final report concise: do not repeat scripts,
patches, commands or tool output in prose. Use approved helpers and focused tool
reads; expand reads when failures, truncation or uncertainty need more context.
Preserve necessary implementation, reasoning, tests, diagnostics, evidence and
cleanup. Follow Implementation-Workflow.md#reduce-unnecessary-model-output;
local terminal rendering itself adds no model tokens.
Finish current commands, evidence collection and guarded cleanup before
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

Before ending, update the task's active handoff with the result, reusable
evidence, next action, actual settings, reassessed next model/effort and cleanup state. Reapply task
selection and write Continuation.md for the next eligible task; it may differ
from the task just worked on. Reassess from what is now proven and what remains;
do not copy the current settings automatically. Write exactly one settings line
in Continuation.md in this form, replacing both placeholders, followed by a fresh
reason on the next line:

    - Settings: **`<model>` / `<effort>`**.
      Reason: <why these settings preserve quality for the next bounded result>.

Use one of `gpt-5.6-sol`, `gpt-6-astra`, `gpt-5.6-terra`, `gpt-5.6-luna` and
`low`, `medium`, `high`, `xhigh`, `max` under that policy. The supervisor validates
and uses this choice for the next fresh session without a routing-model call or
another approval pause. Missing, duplicate or unsupported settings stop launch;
there is no silent fallback. Do not claim to switch this running conversation.

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
  Give each finding once and link detailed handoff/evidence; do not generate a
  second prose report before this structured response. Include every material
  failure and recovery detail even when that requires a longer report.
  The supervisor supplies session numbering, completion time and duration from
  its own clock. Do not append the report yourself.

After saving this one slice's handoff, end the turn. The supervisor will verify
the result and start a new Codex session if work remains. When all tasks are
complete, record completion and stop without rerunning accepted suites.
