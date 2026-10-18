# 002 — Installed timer contention and service recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 30–60 minutes.

## Session boundary

Deliver owner loss through budget exhaustion, service restoration and retry.
001 supplies host timer safety; 002a supplies the cumulative Busy histories and
shared fault ownership; 002c supplies within-budget owner reactivation and native
service restoration mechanics.
Session exception: the real fault, bounded exhaustion, service restoration and
accounting checks form complete histories on two installed targets.

## Purpose and route

Required tasks: 001, 002a, 002c.
Follow the [master](../Reliability-Plan.md),
[screen-time design](../SystemDesign/Screen-Time.md),
[installed runner](../../tests/integration/README.md) and the retained
[usage-read engineering obligation 143](../TestAutomation/E2E-Building-Blocks.md#inventory-reconciliation)
(E2E queue task 172).
Extend `system_session_expiry.py` and its registered session owner, reusing
identity, real authorization, native usage and recovery helpers. Read complete
call chains before choosing the smallest shared fixture extension.

Planned selector (unimplemented): `test_timer_owner_loss_recovery[exhausted]`, area
`session`. Register canonical cases once;
reuse existing exact coverage and retain obligation 143's separate status.

## Finite history and expected results

For a nonzero recorded-use history, exercise daemon idle-owner loss/reactivation
at a read boundary. Hold this fault through bounded exhaustion. Together with
002b/002a and 002c, this retains all four original branches without borrowing a
predecessor's live session.
State the exact native trigger, release/restoration point and original operation deadline in
the registered case before running it. Verify the condition actually occurred
using owned native evidence; a mocked reply is not this acceptance.
Avoid direct edits to usage data. Any necessary fault mechanism belongs in the
engineering fixture with owned restoration, not a production test hook.

Observe the broker helper and child's estimate/resume paths independently.
Exhausted reads retain verified estimates/report unavailability, never zero
usage or a new grant.
While active, no late usage replay may extend the deadline. Restore the real
service and retry the original supported operation; observe
correct balances, continued enforcement and unaffected second-child state.

## Work sequence

1. Establish recorded use, prior estimates and independent second-child controls;
   verify the exact fault identity and original operation deadline.
2. Observe actual owner loss and hold the fault through that deadline. Retain
   the first failure, terminal category and each independent accounting result.
3. Restore service, retry the supported operation and observe balances and
   enforcement before another transition can hide a failure.
4. Verify unrelated-child state/work and complete exact restoration/cleanup.

## Validation and close-out

First run affected host fault/ownership tests, then discover registered selectors
and execute the complete owner-loss exhaustion branch on both targets under the
master's system-acceptance route. Preserve the first failure, native cause,
terminal category, bounded timing, restored service and cleanup receipts.
Fix root causes without loosening identity or error classification. Build after
product edits; register actual coverage in its existing owners and generated
report. No complete customer E2E or obligation-143 close-out is implied.
