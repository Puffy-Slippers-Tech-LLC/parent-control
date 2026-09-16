# 065 — Compose grant-only and combined time profiles

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-010 (25, 26) and E2E-011/grant-only or combined (28, 29). Scope: FLOW13 grant-only/combined scope.

Required implemented capabilities: FLOW13. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Extend FLOW13 to grant-only and combined/grant-dominant using real kiosk approval followed by retained Parent readback. Keep D/G meanings and elapsed/rounding margins explicit.

## Live VM acceptance

On independent VM attempts, observe D=0/G>0 for grant-only and G>D>0 for the declared combined/grant-dominant preparation. Finish at GDM each time without changing the clock or disabling a live grant.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_expiry`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
