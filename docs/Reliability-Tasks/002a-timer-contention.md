# 002a — Native timer contention recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 001.
Estimate: 45–75 minutes.
Session exception: real contention, bounded exhaustion, release and recovery
must retain their original usage history on each of two targets.

## Deliverable and route

Deliver the Busy half of original task 002 through `system_session_expiry.py`
and its canonical session owner. Read complete native usage, authorization,
identity and recovery helpers before extending them. Preserve
[obligation 143](../TestAutomation/E2E-Building-Blocks.md#inventory-reconciliation)
and E2E task 172's wider scope and pending status.
Planned selector (unimplemented): `test_timer_contention_recovery`, area `session`.

Use a supported competing timer-database client and nonzero recorded usage.
Register two finite branches: Busy/recovery and Busy/exhaustion. Declare the
exact native trigger, client identity, release point and original operation
deadline. Prove real reviewed Busy occurred; mocked replies and usage-data edits
cannot qualify it. Fault mechanics belong in the shared engineering fixture,
with recorded restoration and no production test hook.

Observe broker helper and child estimate/resume independently. Temporary faults
recover within existing budgets; exhausted reads retain verified estimates or
report unavailability, never zero use or extra time. No active-use replay may
extend a deadline. Release the client, retry the supported operation and verify
correct balances, enforcement and the unaffected second child's state/work.

## Acceptance and close-out

Run affected host fault/ownership checks before both complete installed branches
on both targets. Discover the registered selector before execution. Retain first
failure, native cause/category, timing, restored-client receipt and owned
cleanup. Follow master build/registration/evidence rules. Close only 002a;
owner-loss/reactivation remains in 002.
