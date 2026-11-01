# 002 — Check native time without the extension

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 001.
Estimate: 45–75 minutes; one native accounting history per target.

Read the [master](../Broker-Expiry-Plan.md), design's historical investigation,
Screen-Time/State owners and complete `TimerUsage.query_native_deadline` call
chain. Extend `test_core` for native arithmetic/failure refusal and the installed
session owner for actual native behavior. Planned system-282 parameter:
`native-time` (unimplemented). Use native public APIs; no production timing
implementation or second ledger in this task.

With the extension endpoint unavailable, observe uninterrupted active daily
usage and repeated fresh reads against one original deadline. Native remaining
time must decrease; reads cannot move expiry forward or checkpoint invented use.
Use daily-only, grant-only and positive D>G>0 estimates to distinguish daily
activity accounting from elapsed grant expiry. A shorter expired/revoked grant
cannot erase positive daily time. Idle/lock/switch observations reuse existing
native activity helpers and reliability resume mechanics. Real suspend/wake
qualification remains with LIFE03 and cases 124/125, an explicit external gate.

Cover status and fixed/rest-of-day calculation inputs, both calling surfaces,
authorization refusal and native unavailability at the lowest effective existing
host/dispatch layer. TIME01/REQUEST08/FLOW05 retain their complete public surface
journeys. Do not repeat their authentication matrix or task 172's reader faults.
If no independent source can supply current use, report that blocker; static
recorded use or the disabled extension's endpoint cannot qualify independence.

Prepare the native reader and ordinary foreground activity under ample setup
entitlement before starting the measured interval. Bracket fresh reads with
monotonic timestamps and native precision; require meaningful progress over the
interval, not an exact tick or two back-to-back reads differing. Arm any short
grant-expiry observation only once its reader is ready.

Run affected host checks and this installed parameter on both targets; restore
exact original native limits/grants and extension state through owned cleanup.
Timing estimates establish no lock, app-access or customer-case pass.
