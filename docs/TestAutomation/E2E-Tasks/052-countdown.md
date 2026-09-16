# 052 — Read the child desktop countdown

Budget: 20–40 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015/kiosk-approved (49), then E2E-005 (7–12) and E2E-011 (27). Scope: TIME01's child-desktop snapshots.

Required implemented capabilities: FLOW02 and intended-child fresh login. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Register bounded child-desktop countdown text and return an explicit observation for the caller's expected balance. Qualify this public projection independently of lock entry, retained unlock, absence on other surfaces and tick measurement.

## Live VM acceptance

Prepare positive child time publicly on the VM, enter the child fresh and read the displayed countdown within declared elapsed-time/rounding bounds. Repeat from an independently reached child desktop. A wrong account or surface must refuse this projection; absence on lock, GDM and other-user surfaces is qualified separately.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_countdown`, or the complete named consumer if
runnable. Reuse the master's guarded qualification route. Require every stated
result and owned cleanup on the live VM; diagnostic success earns no scenario
coverage.

## Close out

After successful cleanup, update the callable, qualified scope and remaining
work in [the catalogue](../E2E-Building-Blocks.md), then check this task in the
[master](../E2E-Execution-Plan.md). If the complete E2E consumer also passed, run
`tools/generate_test_coverage.sh` (the launcher for
`tools/generate_test_coverage.py`) before checking it off. Delete this task when
no longer needed, replacing its master link with plain text. No new evidence or
history document. Follow the master's Markdown checks.
