# 003 — Daily accounting across inactivity and delayed resume

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and route

Required tasks: 001, 002.
Read the [master](../Reliability-Plan.md),
[screen-time accounting/compatibility contract](../SystemDesign/Screen-Time.md),
[shared countdown support](../../tests/support/README.md#host-and-guest-boundaries)
and exact TIME01–TIME04/retained-entry bindings in the
[building blocks](../TestAutomation/E2E-Building-Blocks.md).
Reuse `countdown_qualification.py`, immutable `CountdownSample` comparisons,
`real_interval.py`, `desktop_session.py` and their installed worker. Product
previews omit the resume controller and cannot establish this result.

Planned qualification (unimplemented):
`check_e2e_daily_resume_accounting` under the existing countdown qualification
owner. This is engineering qualification, not completion of E2E-011/022.

## Finite history and expected results

Use two independent attempts with a public four-minute daily allowance and
observed zero initial grant: daily-only, and combined daily/grant time. In the
combined attempt approve one additional 60 seconds before the first interval;
the broker's actual fixed-grant arithmetic, not the requested addition alone,
defines its original deadline. Require sufficient independently observed daily
balance for the declared intervals before starting; unexpected prior usage is
a preparation failure, never permission to erase it. Capture both daily and
grant balances. In each attempt retain recognizable work, perform two
20-second active / 70-second locked-inactive intervals, return normally and
check each endpoint before another transition can repair it. Use native activity
observations to distinguish inactivity from an assumed lack of input.

The daily balance follows actual recorded activity and excludes observed
inactivity; the grant keeps elapsing at its original deadline. The combined
attempt must reach a proven daily-dominant endpoint after the inactive intervals,
without issuing a second grant. Use controller monotonic read brackets,
read-only native usage/grant corroboration and existing declared display
precision/tolerance. Compare balance intervals across inactivity; the active
tick-progression helper alone cannot assert daily accounting, and minute
rounding can legitimately hide a 20-second decrease.
No countdown restart, unearned increase, premature lock while usable time remains
or active-use replay is allowed. Complete natural exhaustion with no new grant
and observe the native lock. Retain the other child's independent state/work.
Compose one delayed boundary from task 002 without replacing the real accounting
oracle with injected usage. Each intermediate result is mandatory.

## Validation and close-out

Extend shared mechanics before cases and validate their ownership/input/timeout
guards at host scope. Qualify changed exact bindings and both complete attempts
on both targets with renewed child sessions. Keep original attempt/time bounds;
missing input margins fail preparation rather than changing the clock.
Fix demonstrated product or native-compatibility handling defects reproducibly;
preserving a cached deadline alone is not proof of correct accounting. Build as
required, retain exact reports and cleanup, and update existing qualification
owners without changing customer case completion.
