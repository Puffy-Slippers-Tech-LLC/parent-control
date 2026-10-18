# 002b — Native timer contention within budget

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 001.
Estimate: 30–60 minutes.
Session exception: real contention, release, recovery and independent accounting
controls form one complete installed history on each target.

## Deliverable and route

Extract the Busy/recovery branch from 002a. Read the
[screen-time accounting contract](../SystemDesign/Screen-Time.md),
`system_session_expiry.py`, its canonical session owner and complete native
usage, identity, authorization and fault-restoration helpers. Keep one shared
engineering competing-client fixture, without a production test hook.
Planned selector (unimplemented):
`test_timer_contention_recovery[within_budget]`, area `session`.
Discover its actual registration before running it.

## Work sequence

1. Establish nonzero native recorded use, a verified prior estimate and the
   second child's independent state/work in a fresh attempt. Declare the
   competing client's exact identity, native trigger, release point and original
   operation deadline before inducing contention.
2. Use a supported competing timer-database client. Retain native evidence of
   the reviewed Busy result; fake replies and usage-data edits cannot qualify it.
3. Release contention within the existing retry budget. Independently observe
   broker-helper and child estimate/resume recovery without resetting attempts,
   extending deadlines, inventing zero use or replaying during continuous activity.
4. Verify correct balances, continued enforcement and unaffected second-child
   state/work. Restore only the recorded fault and complete owned cleanup.

## Acceptance and close-out

Run affected host fault/input/ownership checks before the complete installed
branch on both targets. Retain first failure, native cause/category, dispatch
timing, independent results and restoration/cleanup receipts. Repair demonstrated
root causes and follow master build, registration and evidence rules. Close only
002b; 002a owns sustained Busy through budget exhaustion and later supported retry.
Preserve obligation 143 and E2E task 172's wider assertions and pending status.
