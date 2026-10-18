# 002 — Installed timer contention and service recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 45–75 minutes.

## Session boundary

Deliver native owner-loss/reactivation recovery and exhaustion. Task 002a
supplies the separate Busy histories and shared native-fault ownership mechanics.
Session exception: the real fault, bounded exhaustion, service restoration and
accounting checks form complete histories on two installed targets.

## Purpose and route

Required tasks: 001, 002a.
Follow the [master](../Reliability-Plan.md),
[screen-time design](../SystemDesign/Screen-Time.md),
[installed runner](../../tests/integration/README.md) and the retained
[usage-read engineering obligation 143](../TestAutomation/E2E-Building-Blocks.md#inventory-reconciliation)
(E2E queue task 172).
Extend `system_session_expiry.py` and its registered session owner, reusing
identity, real authorization, native usage and recovery helpers. Read complete
call chains before choosing the smallest shared fixture extension.

Planned selector (unimplemented): `test_timer_owner_loss_recovery`, area
`session`. Register canonical cases once;
reuse existing exact coverage and retain obligation 143's separate status.

## Finite history and expected results

For a nonzero recorded-use history, exercise daemon idle-owner loss/reactivation
at a read boundary. Cover temporary recovery and bounded exhaustion separately:
owner-loss/recovery and owner-loss/exhaustion. Together with 002a these retain
all four original branches, without borrowing a predecessor's live session.
State the exact native trigger, release/restoration point and original operation deadline in
the registered case before running it. Verify the condition actually occurred
using owned native evidence; a mocked reply is not this acceptance.
Avoid direct edits to usage data. Any necessary fault mechanism belongs in the
engineering fixture with owned restoration, not a production test hook.

Observe the broker helper and child's estimate/resume paths independently.
Reads must recover within their existing total budgets; exhausted reads retain
verified estimates/report unavailability, never zero usage or a new grant.
While active, no late usage replay may extend the deadline. Restore the real
service and retry the original supported operation; observe
correct balances, continued enforcement and unaffected second-child state.

## Validation and close-out

First run affected host fault/ownership tests, then discover registered selectors
and execute both owner-loss branches on both targets under the
master's system-acceptance route. Preserve the first failure, native cause,
terminal category, bounded timing, restored service and cleanup receipts.
Fix root causes without loosening identity or error classification. Build after
product edits; register actual coverage in its existing owners and generated
report. No complete customer E2E or obligation-143 close-out is implied.
