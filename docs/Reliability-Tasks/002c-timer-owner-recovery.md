# 002c — Native timer owner reactivation within budget

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 001, 002a.
Estimate: 30–60 minutes.
Session exception: actual owner loss, reactivation and independent accounting
controls form one complete installed history on each target.

## Deliverable and route

Extract owner-loss/recovery from 002. 001 supplies host timer safety; 002a
supplies cumulative native fault ownership, restored-client and accounting
controls. Read the [screen-time contract](../SystemDesign/Screen-Time.md),
`system_session_expiry.py`, its registered session owner and complete native
service/identity/authorization/restoration helpers before extending them.
Planned selector (unimplemented):
`test_timer_owner_loss_recovery[within_budget]`, area `session`.

## Work sequence

1. Establish nonzero recorded use, a prior verified estimate and second-child
   state/work in a fresh attempt. Declare the exact native owner-loss trigger,
   restoration point and original operation deadline in the registered case.
2. Exercise daemon idle-owner loss at a read boundary and prove it occurred
   using native evidence. Reactivate the real service within existing budgets;
   do not substitute mocked errors, edit usage data or reset attempt counts.
3. Independently observe broker-helper and child estimate/resume recovery,
   correct balances and enforcement. No failed read becomes zero use, grants
   stay unchanged and active-use replay cannot extend the original deadline.
4. Verify the second child's independent state/work, restore the exact owned
   service fault and complete cleanup. Reuse shared fixture mechanics, never
   a predecessor's live session or production test hook.

## Acceptance and close-out

Run affected host fault/ownership guards, discover the actual selector and run
the complete branch on both targets. Preserve first failure, native cause/category,
bounded timing, independent results and restored-service/cleanup receipts.
Repair demonstrated root causes and follow master build/registration/evidence
rules. Close only 002c; 002 owns owner-loss exhaustion and subsequent retry.
Preserve obligation 143 and E2E task 172's wider scope and pending status.
