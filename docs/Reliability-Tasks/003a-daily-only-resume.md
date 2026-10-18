# 003a — Daily-only inactivity accounting

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 001.
Estimate: 45–75 minutes.
Session exception: active/inactive accounting through natural exhaustion is one
complete renewed-session history per target.

## Deliverable and route

Reproduce the cached-deadline/activity gap behind `d4df2187` and `5b15f17d` with
a daily-only allowance. This history needs actual native accounting, not the
unrelated contention fixture from 002. Read
[screen-time accounting](../SystemDesign/Screen-Time.md), exact TIME01–TIME04
bindings in [building blocks](../TestAutomation/E2E-Building-Blocks.md) and shared
countdown/session helpers. Extend `countdown_qualification.py`, immutable
`CountdownSample` comparisons, `real_interval.py`, `desktop_session.py` and the
installed worker. Planned qualification (unimplemented):
`check_e2e_daily_only_resume_accounting`, independently registered under the
existing countdown owner. It does not close E2E-011/022.

Publicly configure a four-minute daily allowance with observed zero grant and
sufficient independently observed starting daily balance. Retain recognizable
work; perform two 20-second active / 70-second locked-inactive intervals. Use
native activity observations and capture each endpoint before another
transition. Compare monotonic read brackets with read-only native usage/grant
corroboration and declared display tolerances; minute rounding may hide a
20-second decrease. Daily balance excludes observed inactivity and follows
recorded activity. No grant, countdown restart or unearned increase is allowed;
usable time must not lock prematurely.

Complete natural exhaustion and observe native lock. Independently retain the
second child's state/work. Do not erase usage, change clocks or substitute tick
progression for accounting. Combined grants and delayed native reads remain in 003.

## Work sequence

1. Verify the renewed session, public daily-only profile, zero grant, starting
   balance and recognizable work for both children before measuring activity.
2. Complete the first active/inactive interval and compare its native activity,
   balance and monotonic read brackets before starting the second interval.
3. Complete the second interval with the same independent comparisons; retain
   any early lock or unearned increase as a failure.
4. Continue to natural exhaustion, observe native lock and the second child's
   preserved state/work, then complete owned cleanup.

## Acceptance and close-out

Validate shared comparison/input/ownership guards at host scope, then the
complete daily-only history on both targets with renewed sessions. Insufficient
starting margins fail preparation. Retain intermediate results and cleanup,
repair demonstrated root causes, and follow master build/evidence/coverage rules.
Close only 003a.
