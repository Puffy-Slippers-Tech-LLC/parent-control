# 197 — Approve more time and return to the child's activity

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW20 overlay new/open form**. First scheduled consumer: [E2E-048, case 223](../E2E-Scenario-Recipes.md#e2e-048).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048d** — Fixed overlay AUTH01/02, explicit approval and automatic original-activity return.
- **052** — TIME01 child-desktop presence and limits-off absence.

## Implementation

Inspect [313's shared delivery](../E2E-Building-Blocks.md#cross-plan-baseline-reuse)
and reuse applicable request, grant/countdown and entry leaves. Its fixed kiosk
Riley/Jamie/600-second/soft-included history does not qualify this parameterized
overlay composition. Implement only missing arguments/results, without a second
shared authentication or countdown implementation.

Compose the overlay branches of FLOW04 and FLOW05, then TIME01/UI12 on the same child desktop. Accept explicit new/open form entry and earlier public balance observations. No hidden allowance, policy preparation or desktop transition. Keep the kiosk branch pending.

Reuse `request_flow.prepared_request`, `overlay_approved_request` and
`KioskRequestJourney.check_countdown`. The existing request leaves accept only
Riley/Jamie/75 seconds/soft included on overlay, with separate finite 600-second
kiosk work in 313; implement and qualify the remaining FLOW20 explicit
child, eligible-parent, duration and soft-choice arguments, with public balance
arithmetic, before advertising that scope. Immediate exit,
rejection and Cancel qualifications are not prerequisites of automatic approval.

Expose bounded caller-owned selections for Jordan/Riley, Jamie/Casey (the
recipe's Sam binding), soft excluded/included and the consuming recipes' finite
durations: 30/60/75/120/150/180/900 seconds. This also supplies
[E2E-012's selected approval branches](../E2E-Scenario-Recipes.md#e2e-012) and
the selected bindings in E2E-048/049/050/051. Carry the explicit child through
form/recipient authentication, activity identity and countdown comparisons;
never infer it from a fixed wrapper or substitute a remembered approver.
Qualify new-form Riley/Jamie/30-second/soft-excluded approval and independently
open-form Jordan/Casey/75-second/soft-included approval, with fresh exact
request/recipient proofs and public time increments. Reuse immutable activity
endpoints. Do not multiply independent values into every combination;
each later case owns its finite selection, policy outcome and complete acceptance.

## Live VM acceptance

In separate live attempts, supply a usable child desktop for the declared new-form binding and an independently prepared overlay for the declared open-form binding. Approve once per invocation, observe automatic form disappearance and the same usable child desktop, then compare countdown with the earlier public balance plus the requested interval and measured elapsed time. Missing, wrong-child or kiosk entry refuses without preparatory input.

Implemented qualification selector (live qualification pending):

```sh
tools/run-tests integration check_e2e_compose_approval_and_return_to_the_child
```

Current source route: `request_flow.approval_and_return` composes the existing
FLOW04/05 leaves. `JourneyPlan.overlay_request` carries the explicit
child/approver/duration/soft tuple through `UiObservations`, `AccessibleUI` and
the existing Shell credential recipient guards. `approval_return.NEW_PLAN` and
`OPEN_PLAN` bind the two independent entries; `ApprovalReturnJourney` reuses
`KioskRequestJourney.check_countdown` and compares canonical public seconds
before/after the one approval, allowing measured elapsed time and two seconds.
The original immutable activity endpoint is compared after automatic return.
The selector also runs the affected fixed English and Hebrew approval regressions
in their own restored attempts. No complete scenario is registered by this task.

## Current handoff

Two unsuccessful live attempts have occurred. The second advanced beyond
`flow20-new-overlay-approval-result`: explicit approval and automatic return to
Riley's desktop passed. The first failure was a mechanical observer defect:
`kiosk-result-child-<uid>` is visible only on restart notices, so approval must
use its explicit success message, verified child session and pinned request
window. Those guards remain intact. The 143 affected host checks and
source/traceability validation passed after this correction.

The current failure is `flow20-new-overlay-countdown-increment`, stage
`countdown`, category `overlay-return:public-increment`. The furthest independently
verified checkpoint is `flow20-new-overlay-automatic-desktop-return`, stage
`returned`. The added-time assertion failed. Later maintenance sessions
established pending daily-use accounting as the cause; no supported correction
has been codified. Original
activity comparison after return, Jordan/Casey's independent open entry and
the fixed approval regressions did not run.

The formal runner failure is retained in
`output/test-runs/host/reports/20261030T165801Z-56512acc/failure.json`;
normal private diagnostics are in
`output/test-runs/privileged/allocations/onpc-graphical-smoke-pl7tadq5` and
`output/test-runs/privileged/allocations/onpc-e2e-evidence-q2pfrn_y`.
Worker/callback closure, outer cleanup, baseline restoration and host/source
preservation passed for that formal attempt. A watch collector timeout was
logged during its cleanup. The original selector requires `--resume` to recover
its retained family claim. Keep this task unchecked until all selected
acceptance passes.

The third session reproduced the same daily-only history through the maintained
`tools/test-vm --vm onpc-Ubuntu26.04 reproduce-overlay-return` route. It retained
the scene before the countdown assertion in
`output/test-runs/privileged/allocations/onpc-overlay-return-diagnosis-c6g0z8eu`;
the worker and callback closed. This is diagnosis, not a new formal acceptance
attempt. Riley's countdown was 1769 seconds at guest monotonic 443573389871 ns
and 1822 seconds at 520389734369 ns: elapsed 76.816 seconds, expected about
1722 seconds. The immutable observations and `boundary-observation.json`
retain those values. Approval and automatic return passed again.

The product's calculation used an older daily-use total. The broker log recorded
daily=1799, grant=0, additional=30, calculated=1829, while the child log's
previous remaining value was 1699. Queries executed as Riley on Riley's session
and system buses then returned daily=1699 and a completed usage interval ending
at grant issuance. Riley's session was active, unlocked and not idle. The
canonical countdown API computes seconds at read time, so stale display text
does not explain the discrepancy. Product source and the installed GNOME
manager show that approval reads completed intervals before the native grant
change checkpoints the still-active interval.

Two controlled native-property probes preserved the original grant. Rewriting
the unchanged 1800-second daily limit left the completed interval and daily=1699
unchanged. Temporarily changing it to 1801 seconds advanced the interval end and
daily became 1486; restoring 1800 gave daily=1485. The limit was restored in a
`finally` block. This establishes pending-use checkpointing as the cause; policy
churn is not a supported correction. The installed manager exposes no public
flush operation among its inspected methods. No product code or assertion has
been changed for this accounting issue.

The fourth session implemented the pre-approval diagnostic boundary:
`reproduce_overlay_return` now stops at `approval-open`, with
`boundary_operation=None`, after the prepared form and estimate but before
Request input. The shared worker and callback closed, retaining the scene in
`output/test-runs/privileged/allocations/onpc-overlay-return-diagnosis-8j2w133w`;
worker evidence is `output/test-runs/privileged/allocations/onpc-e2e-evidence-ovurekgf`.
The real acceptance plan and its two-second assertion are unchanged.

Fresh queries as Riley found no completed usage record before approval:
`QueryUsage=[]`, daily=1800, grant=0, canonical countdown=1715 at guest monotonic
413825064857 ns. The planned exact-record replay therefore refused before any
write; no record was invented. GNOME's saved history still contained only old
snapshot entries and did not supply the current active interval.

A controlled public logind `SetIdleHint(true)` made the aggregate user idle and
GNOME recorded the real interval `[1793382320,1793382490]`. Daily became 1630,
matching the pre-inactivity countdown, without changing policy or grants.
The session's original false idle hint was restored in `finally`. After resume
and twelve seconds of activity, replaying that exact interval left both usage
and daily=1630 unchanged. The countdown increased from 1615 at monotonic
517792584684 ns to 1629 at 518969312926 ns. Thus exact-record replay refreshes
the stale estimate rather than checkpointing ongoing use; reject it as this
approval correction. Both operations ran through guarded `exec`; these are
engineering observations, not acceptance.

A second controlled experiment activated Jamie's existing session and restored
Riley's in `finally`. Riley's public user state changed active → online → active
and session Active changed true → false → true, but all login and idle timestamps
stayed unchanged. `IdleSinceHint=1793382494182795` and
`Timestamp=1793382318042628` do not identify the resumed activity start.
A stateless lookup of those timestamps is therefore insufficient. Native saved
history and completed usage also remained unchanged at the later read; do not
infer a new product defect from that short supporting experiment.

Next discriminating fix experiment: recreate a clean original history, capture
the actual native balance at the authenticated broker calculation in the real
child's bus context, and temporarily cap the stale daily operand with it while
preserving the broker-owned live grant. Test whether that one causal change
restores the exact additional-time result without usage writes or policy churn.
`CalculateOwnRemainingTime` already combines a child-supplied native allowance
with the root-owned grant; inspect that trust boundary before choosing a
maintained integration. This experiment and its supported product API are not
implemented. Never use a cached expected test value, invented interval,
private GNOME method or weaker assertion as the correction.

The diagnostic launcher now checks its named package input before fixture
construction. The missing current input was prepared through the artifact
builder, and the installed test dispatcher was refreshed through setup.
The 63 existing overlay safety checks, 39 scoped maintenance safety checks and
source/traceability passed in the third session. A broader maintenance-unit selection was cancelled
through the maintained launcher and replaced by that scoped selection; owned
shutdown finished. No excluded non-product coverage was restored, no product
build inputs changed, and no backend review was needed. Formal VM acceptance
and task close-out remain pending after a supported correction.
The fourth session prepared its new source-bound package input with the
maintained artifact builder, then passed the same 39 scoped maintenance safety
checks and source/traceability after the boundary change. No tests were added,
no product source or package/build inputs changed, and no backend review was
needed. Formal acceptance remains the second session's failed result; the
fourth session added diagnostic evidence only.
Maintenance stop restored the baseline successfully. The controlled idle hint
and session selection were restored before stop; no experiment or maintenance
ownership is handed to the next session.
