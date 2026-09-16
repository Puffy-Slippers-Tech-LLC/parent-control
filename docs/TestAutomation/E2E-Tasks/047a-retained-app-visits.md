# 047a — Compose retained app visits for distinct users

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-005/006 isolation and later retained-activity journeys.
Scope: FLOW09 and FLOW14 for a finite set of distinct users.

Required capabilities: APP04, FLOW08, DESK03/09/10 and FLOW15's fresh/retained
entries. Resolve maintained callables from the
[catalogue](../E2E-Building-Blocks.md#reusable-journey-fragments). Each attempt
starts fresh with explicit public time/policy prerequisites; no previous task
document or VM state is an input.

## Work

Compose FLOW09 from legitimate retained entry, APP04 comparison and APP03 use.
Compose FLOW14 from the explicit per-user entry, FLOW08, activity capture and
Switch User sequence. Carry the prior observations and current surface; do not
replace an existing desktop or relaunch an app to satisfy continuity.
Same-child multiple desktops retain their separate gate.

## Live VM acceptance

On the installed VM, prepare and capture recognizable activities for the child
and declared other user, preserving both through normal Switch User. Return
legitimately to each original desktop and prove the same activity remains
usable. FLOW14 starts and ends at GDM; FLOW09 ends at the named usable activity.
Independent retained entry must work; a missing prior observation or wrong
entry mode refuses without recreating state.

Run affected checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_allowance` in the master's guarded
envelope. Require all stated results and owned cleanup. No partial scenario
registration or backend activity probes.

## Close out

After successful cleanup, update callable/scope/status in
[the catalogue](../E2E-Building-Blocks.md) and check this task in the
[master](../E2E-Execution-Plan.md). If a complete E2E consumer also passed, run
`tools/generate_test_coverage.sh` (the launcher for
`tools/generate_test_coverage.py`) before checking its scenario.
Delete this file once enduring context is maintained elsewhere, replace its
master link with plain text, and validate changed Markdown. No new evidence or
history document.
