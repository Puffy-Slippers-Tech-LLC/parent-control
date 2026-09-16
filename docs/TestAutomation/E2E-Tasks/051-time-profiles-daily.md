# 051 — Compose the daily-only time profile

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-011/daily-only (27), then E2E-008 (21, 22). Scope: FLOW13 daily-only.

Required implemented capabilities: PARENT17, PARENT18; PARENT09, FLOW02; FLOW05, FLOW06, FLOW07; DESK09/10; FLOW15 and FLOW01 retained scopes. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement FLOW13's daily-only branch using observed no-grant state (or declared normal revocation), FLOW02 and final GDM return. Keep explicit parent/window entry and balance observations. Grant branches remain pending.

## Live VM acceptance

On the VM establish daily-only time from public controls, read D>0 and no one-time balance, then finish at GDM. Re-enter with the declared retained Parent window and reproduce the profile without hidden preparation.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_expiry`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
