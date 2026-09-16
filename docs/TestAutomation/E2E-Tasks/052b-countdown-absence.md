# 052b — Prove countdown absence on other surfaces

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-011/daily-only (27), then grant-only/combined (28, 29).
Scope: TIME01's stable-absence projections on lock, GDM and another user's desktop.

Required capabilities: child-desktop TIME01, FLOW02, intended-child fresh entry,
DESK05/06/08/11 and the declared other-user entry. Resolve callables from the
[catalogue](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries).
No previous task document or attempt supplies context.

## Work

Bind complete, fresh absence observations to each positively identified surface.
A disconnected observer, inaccessible tree or wrong surface cannot prove absence.
Keep input routes outside TIME01; it only observes the caller's stated surface.

## Live VM acceptance

In a fresh installed VM attempt, prepare ample positive daily time publicly,
enter the child and read its countdown. Lock normally and require countdown
absence on the identified lock surface. Unlock legitimately and observe the
countdown again. Switch User to GDM and require absence, then enter the named
other user and require absence on that desktop. Qualify independently reached
entry states and wrong-surface refusal. No natural-expiry or tick claim is made.

Run affected checks and the planned fixed qualification
`tools/run-tests integration check_e2e_countdown` through the master's guarded
envelope. Every stated result and owned cleanup must pass; this slice is not
a complete customer scenario.

## Close out

After live acceptance and owned cleanup pass, update the callable, qualified
scope and remaining work in [the catalogue](../E2E-Building-Blocks.md), then
check this task in the [master](../E2E-Execution-Plan.md). If a complete E2E
consumer also passed, run `tools/generate_test_coverage.sh` (the approved launcher
for `tools/generate_test_coverage.py`) before checking off its scenario.
Delete this file when no longer needed and replace its master link with plain
text. No new evidence/history document. Validate changed Markdown as the master
requires.
