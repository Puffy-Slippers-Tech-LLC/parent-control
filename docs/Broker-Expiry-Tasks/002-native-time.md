# 002 — Check live timing without the extension

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 001, 001a, 001b.
Estimate: 45–75 minutes; one native-history/live-observation history per target.

Scheduling: deferred until row 4 has a qualified, bounded implementation. The
[timing exploration](../SystemDesign/Replace-Main.timeLimitsManager.md) owns the
candidate public-input composition; this task implements no observer or native
changes. Review completion alone does not activate this installed qualification.

Read the [master](../Broker-Expiry-Plan.md), timing exploration and retained investigation,
Screen-Time/State owners and complete `TimerUsage.query_native_deadline` call
chain. Extend `test_core` for native arithmetic/failure refusal and the installed
session owner for actual native behavior. Planned system-282 parameter:
`native-time` (unimplemented; historical parameter name). Use the confirmed
existing public inputs and delivered row 4 adapter; no production timing
implementation, native package change or second ledger belongs in this task.

With the extension endpoint unavailable, observe uninterrupted active daily
usage and repeated fresh reads against one original deadline. Computed remaining
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

Prepare the delivered timing reader and ordinary foreground activity under ample setup
entitlement before starting the measured interval. Bracket fresh reads with
monotonic timestamps and native precision; require meaningful progress over the
interval, not an exact tick or two back-to-back reads differing. Arm any short
grant-expiry observation only once its reader is ready.

Run affected host checks and this installed parameter on both targets; restore
exact original native limits/grants and extension state through owned cleanup.
Timing estimates establish no lock, app-access or customer-case pass.

## Current limit

The previous session's affected core checks passed (168 tests), including
repeated consumption of one native deadline and refusal when that reader is
unavailable. Source review found
no independent live daily-time API: Malcontent 0.14 calculates fresh estimates
from completed usage intervals, while GNOME Shell keeps the uninterrupted-use
deadline in memory. The current helper exports that deadline through the child
extension. Fresh daemon estimates cannot replace it without moving expiry
forward. See the [native estimate implementation](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/child-timer-service.c#L1325)
and [Shell's accounting explanation](https://github.com/GNOME/gnome-shell/blob/50.1/js/misc/timeLimitsManager.js#L274).

`native-time` remains unimplemented; neither target has an installed result.
Resume only after the existing-input composition has a supported contract and
bounded delivery, with startup/overlap/recovery handling established. Upstream
changes and replacing Malcontent are forbidden. If current state/history cannot
establish live use, retain the exact blocker instead of guessing it. Reviews
[001a0](001a0-live-time-support.md) and [001a](001a-live-time-source.md) own the
decision; [001b](001b-live-time-reader.md) retains deferred delivery. This task
remains deferred and unchecked until its prerequisites pass and it is explicitly
reactivated under the master. Preserve all
assertions above and the existing changes in `tests/unit/test_core.py`; the host
checks grant no installed acceptance. No VM or persistent test process was
started while preparing this prerequisite plan, and no cleanup remains from
that work.
