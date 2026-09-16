# 043 — Qualify fresh child login and time denial

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015/kiosk-approved (49), then E2E-008/fresh-login (22). Scope: GDM06/07, DESK01 and FLOW15's fresh entry for the intended child; DESK11's rejected-GDM return.

Required implemented capabilities: DESK03/04, UI19/GDM05's repeated challenge context, PARENT08 and FLOW02. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Bind the intended child's fresh GDM recipient, success and explicit time-limit denial. Reuse two fresh recipient proofs and sealed single-use input. Then bind FLOW15(gdm, child, fresh, expected result) to that qualified GDM07 path. Implement DESK11's normal Back/Cancel route from the observed rejected sign-in screen.

## Live VM acceptance

In separate live attempts, use Parent controls to prepare positive daily time or zero daily/no grant, then Switch User and perform a fresh child login through FLOW15. Require a usable child desktop for the former and the specific time-limit rejection after correct authentication for the latter. Return normally from rejection to GDM. Generic authentication failure is insufficient.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_expiry`, or the complete named consumer if
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
