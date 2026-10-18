# 002a — Native timer contention recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 001, 002b.
Estimate: 30–60 minutes.

## Session boundary

Deliver Busy through budget exhaustion, followed by release and supported retry.
001 supplies host timer safety; 002b supplies within-budget Busy recovery and
shared competing-client ownership/restoration mechanics. Session exception:
exhaustion, release and retry must retain one original usage history per target.

## Deliverable and route

Deliver the Busy half of original task 002 through `system_session_expiry.py`
and its canonical session owner. Read complete native usage, authorization,
identity and recovery helpers before extending them. Preserve
[obligation 143](../TestAutomation/E2E-Building-Blocks.md#inventory-reconciliation)
and E2E task 172's wider scope and pending status.
Planned selector (unimplemented):
`test_timer_contention_recovery[exhausted]`, area `session`.

Use a supported competing timer-database client and nonzero recorded usage.
Register only the remaining Busy/exhaustion branch. Declare the
exact native trigger, client identity, release point and original operation
deadline. Prove real reviewed Busy occurred; mocked replies and usage-data edits
cannot qualify it. Fault mechanics belong in the shared engineering fixture,
with recorded restoration and no production test hook.

## Work sequence

1. Verify the recorded-use and second-child controls, exact competing-client
   identity and original deadline before inducing the shared native fault.
2. Hold real Busy through the original budget. Observe broker-helper and child
   estimate/resume outcomes independently: retain verified estimates or report
   unavailability, never zero use or extra time. No active-use replay may extend
   a deadline.
3. Release the client after exhaustion, retry the supported operation and verify
   correct balances, enforcement and unaffected second-child state/work.
4. Restore the recorded client state and finish owned cleanup. Do not inherit
   002b's live client or VM state; its evidence supplies only its qualified slice.

## Acceptance and close-out

Run affected host fault/ownership checks before the complete exhaustion branch
on both targets. Discover the registered selector before execution. Retain first
failure, native cause/category, timing, restored-client receipt and owned
cleanup. Follow master build/registration/evidence rules. Close only 002a;
owner-loss/reactivation remains in 002.
