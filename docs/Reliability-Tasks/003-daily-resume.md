# 003 — Daily accounting across inactivity and delayed resume

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 45–75 minutes.

## Session boundary

Deliver combined daily/grant accounting with one delayed native read boundary.
003a supplies independently qualified daily-only accounting and shared interval
comparisons. Session exception: each target needs a complete active/inactive,
daily-dominant and natural-exhaustion history in one renewed session.

## Purpose and route

Required tasks: 001, 002, 003a.
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
owner, for the combined binding. Task 003a owns the separate daily-only binding.
This is engineering qualification, not completion of E2E-011/022.

## Finite history and expected results

Use one renewed attempt per target with a public four-minute daily allowance and
observed zero initial grant. Approve one additional 60 seconds before the first
interval; the broker's actual fixed-grant arithmetic, not the requested addition alone,
defines its original deadline. Require sufficient independently observed daily
balance for the declared intervals before starting; unexpected prior usage is
a preparation failure, never permission to erase it. Capture both daily and
grant balances. Retain recognizable work, perform two
20-second active / 70-second locked-inactive intervals, return normally and
check each endpoint before another transition can repair it. Use native activity
observations to distinguish inactivity from an assumed lack of input.

The daily balance follows actual recorded activity and excludes observed
inactivity; the grant keeps elapsing at its original deadline. The attempt must
reach a proven daily-dominant endpoint after the inactive intervals,
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

## Work sequence

1. Verify renewed-session inputs and both children's work; obtain the one
   declared approval and record its actual grant deadline before measuring.
2. Complete the first active/inactive interval, including the one declared
   delayed native-read boundary. Compare both balances before proceeding.
3. Complete the second interval and prove the daily-dominant endpoint using
   native activity and balance brackets, without another grant.
4. Continue to natural exhaustion, observe native lock and independent
   second-child state/work, then complete owned cleanup.

## Validation and close-out

Extend shared mechanics before cases and validate their ownership/input/timeout
guards at host scope. Qualify changed exact bindings and the complete combined
attempt on both targets with renewed child sessions. Keep original attempt/time bounds;
missing input margins fail preparation rather than changing the clock.
Fix demonstrated product or native-compatibility handling defects reproducibly;
preserving a cached deadline alone is not proof of correct accounting. Build as
required, retain exact reports and cleanup, and update existing qualification
owners without changing customer case completion.
