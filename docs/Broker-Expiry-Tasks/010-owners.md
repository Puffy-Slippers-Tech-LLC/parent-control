# 010 — Check expiry after the timer restarts

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 005, 007.
Estimate: 30–60 minutes; timer replacement and recovery per target.

Read the [master](../Broker-Expiry-Plan.md), installed session/timer ownership
and reliability 002 owner-loss scope. Extend system-282 with planned parameter
`expiry-timer-owner` (unimplemented). Reuse reliability
and task 172's shared native fault/recovery mechanics; do not duplicate Busy,
reader authorization, identity or generic owner-loss matrices.

Replace the native timer owner at its actual process boundary during usable
active time, spanning the original expiry. Identity-record the old and new
owners; spoofed callbacks alone cannot qualify native reconnection.
Observe protection through the outage and reconstruction from current native
state within original budgets. Old replies/effects must not reach a replaced
session; neither reconnect nor repeated reads may extend time or award usage.

Use the minimum supported real replacement needed to exercise the boundary.
Run this delta on both targets and restore owned process/service
state with the established recovery route. No broader E2E residual is closed.
