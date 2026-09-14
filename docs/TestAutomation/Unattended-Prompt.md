Continue the next unfinished task in docs/Test-Automation.md on this development/
host machine. This is one slice of the user's authorized unattended loop to
finish the authoritative checklist, including the existing guarded test-VM scope.
Per-session “Go ahead” and settings approval are already given. Use the exact
supervisor-supplied model/effort with Standard processing; do not claim to switch
this conversation's model.

The 2026-09-14 operator scope prioritizes customer E2E across all product
surfaces. Timeout/login rejection is only an example. Follow
docs/TestAutomation/E2E-Coverage.md: operate and observe as a real customer;
no backend product assertions, policy probes or internal fault injection.
Preserve completed unit/component/system tests and existing safety checks.
Mechanical installation/upgrade/removal in Tasks 18/20 retains necessary
internal inspection and follows the customer queue. Deferred policy design,
internal matrices and general infrastructure work are not automatic fallback.

Follow AGENTS.md and docs/TestAutomation/Implementation-Workflow.md, which owns
selection, quality, model reassessment, context/attempt limits, verification,
evidence retention and handoffs. Apply its full procedure; this prompt adds the
unattended protocol. Authorization never overrides execution/Polkit policy,
denials, VM ownership, cleanup guards or decisions outside scope. Never widen
permissions or retry a denied action through another route/session; record the
action and reason in the active handoff.

Read docs/TestAutomation/Continuation.md, the master checklist's unfinished-tasks
section and the relevant task's active handoff/contracts/source. Reuse supplied
unchanged instructions; inspect status and relevant edits, preserving other work.
Before shared infrastructure work, read only the selected Reuse-Map.md row and
its relevant contract, regression and limitation links. Publish changed reusable
findings in the owning contract and affected map links; reconcile qualification
claims with retained evidence before handoff.

At each safe boundary choose the earliest ready unchecked entry in checklist
order within the customer queue, then the mechanical package queue; reconcile
stale continuation pointers and recheck earlier deferrals. Do not require whole
internal or UI task matrices when the selected scenario needs only one helper.
Record each bypassed entry's blocker/dependency evidence and return condition
in its handoff, linked from Continuation.md. Preserve later work when returning
to an earlier ready task. The workflow's all-task VM clearance persists:
historical writer-pause/local-only instructions cannot restore the resolved hold.
Actual runner refusals still need current evidence and scoped diagnosis.

Never read, search, diff, edit or load docs/Test-Automation-Slice-Summary.md,
including through bulk repository operations. Exclude it explicitly. It is the
supervisor's append-only operator log and the separate reviewer's input, not an
implementation handoff. Do not read prior Codex transcripts or supervisor events.

State the next bounded result, verification, budget and actual settings, then
implement and verify one coherent slice toward a named complete customer variant
or mechanical milestone. Freeze customer steps and visible assertions; add
infrastructure only for an actual blocked step. Keep updates concise without repeating
scripts, patches, commands or tool output; expand focused reads and explanations
when correctness requires it. Finish commands, evidence collection and guarded
cleanup before ending; budgets are review points, not permission to kill work.
Do not start another Codex process, reset this chat, invoke/control the launcher
or continue into an unrelated slice. Check off tasks only after every required
deliverable and acceptance check passes; do not delete entries.

You own each scenario's
[runtime registration](E2E-Coverage.md#register-each-runnable-scenario-within-its-implementation-task).
Wire its executable and ready entry in tests/e2e/scenarios.json, verify discovery
through `tools/run-tests e2e --list`, and retain the full scenario's passing run
before claiming completion. `make test-all` automatically selects those ready
entries. Complete registration within the scenario's implementation task; do
not leave it for the operator, a separate launcher task or Task 28. Routine
registration needs no operator intervention. Readiness alone is not a pass.

For blockers, follow the workflow's task selection and cumulative recovery rules.
An actual visible product failure stays failed with customer reproduction and
evidence; do not turn the E2E worker into an internal product investigation.
Continue independent customer cases or record a separate repair decision.
The missing policy-acknowledgement proof is not itself a customer failure.
Task 20 resumes in checklist order under Task-20.md#bounded-recovery--2026-09-11
and its active handoff; retained recovery does not override newer independent-task
priorities. Charge earlier consumers' R1 recovery portions to its persistent
ledger and apply checkpoints to further recovery, without blocking unrelated work.
At a required unmet stop checkpoint, finish owned work/cleanup, save the exact
operator decision, and return status=blocked, blocker=decision with truthful
progress/cleanup. Neither restart, fallback work nor the progress reviewer may
erase that decision. Otherwise return blocked only when no independent ready
work can proceed without outside input.

Save the workflow's active task handoff, then reselect and update Continuation.md
for the next eligible task. Reassess next model and effort from proven and
remaining work instead of copying actual settings. Write exactly one line:

    - Settings: **`<model>` / `<effort>`**.
      Reason: <fresh reason for the next bounded result>.

Allowed models: gpt-5.6-sol, gpt-6-astra, gpt-5.6-terra, gpt-5.6-luna.
Allowed efforts: low, medium, high, xhigh, max. Apply the workflow's model policy:
quality first, allowance second; no historical/blanket pin. Missing, duplicate
or unsupported settings stop launch without fallback. The supervisor uses this
choice unless its separate Astra xHigh review assigns a one-slice Astra xHigh/max
intervention. Follow any supplied breakthrough requirement, report whether it
succeeded, and record ordinary reassessed next settings; the override expires.

Return only the supplied structured schema, with no second prose report:

- status: continue when ready active work remains; complete only when every active
  checklist entry is accepted, with deferred engineering explicitly reported;
  blocked when outside input is needed and no independent
  ready work remains, or an explicit recovery checkpoint requires a decision.
- cleanup_complete: true only after every command started here exits, results
  are collected and required cleanup is confirmed. If uncertain, return false
  and save exact owned identities/recovery state in the handoff; old evidence
  cannot establish current cleanup.
- made_progress: for customer work, true for a completed variant or verified
  reduction of the frozen remaining steps for its named consumer. Distinguish
  helper progress from completed customer coverage. New internal questions,
  added prerequisites, rewritten handoffs and repeated experiments do not count.
  Mechanical work measures its declared qualification milestones separately.
- blocker: none unless blocked; otherwise approval, environment, decision or
  no-ready-task.
- summary: self-contained string fields: task (ID/result pursued), completed
  (completed variant IDs/count, remaining frozen scope, scope transfers,
  consecutive slices without a completed customer variant, and unfinished
  acceptance; mechanical work uses milestone/defect counts), verification (checks, evidence,
  failures and cleanup), next (concrete next action or outside intervention;
  name any different next task). When work continues, end next with
  `Next settings: <model>/<effort>, Standard.`

Follow [Progress-first presentation](Unattended-Sessions.md#cumulative-session-summaries):
the intended first field is progress, rendered before Task with the bold rating
**Solid and healthy** for completed customer outcomes and shrinking frozen
remaining work (or a finite first consumer adapter), or
**Nearly blocked or stalled - need intervention** when the completion horizon
does not improve, two customer slices finish without a completed variant,
prerequisites keep growing or outside input is required. Apply the workflow's
mandatory intervention; do not reset counters across task/model/chat changes.
Judge cumulative task progress from the handoff, not passing helper tests. Put support in
completed/verification and intervention in next. Until the supplied schema and
renderer support progress, use existing fields without adding it or a second
report. Omit time estimates/routine launcher metadata unless an older supervisor's
supplied schema still requires estimates; new presentation needs launcher restart.

Give each finding once, linking detailed handoff/evidence, but include every
material failure/recovery detail even if longer. Use redacted roles, relative
repository paths and test IDs; no names, account identifiers, PII, secrets or raw
transcripts. The supervisor supplies session number/time/duration and appends the
report; never append it yourself.

After saving this slice's handoff and returning the report, end the turn. The
supervisor verifies it and completes a separate progress review before another
implementation session. When all tasks are accepted, record completion and stop
without rerunning accepted suites.
