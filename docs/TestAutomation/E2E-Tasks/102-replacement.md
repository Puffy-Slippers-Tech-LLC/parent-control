# 102 — Compose expiry recovery through kiosk approval

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-009 (23, 24). Scope: FLOW11.

Required implemented capabilities: TIME04, FLOW06, FLOW15, APP02/04/03, FLOW03 and FLOW13 grant profiles. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose DESK11, FLOW06, retained FLOW15 and APP02/04/03 with explicit retained-or-closed expectations. A legitimate unlock must precede activity inspection; the closed branch ends at APP02.

## Live VM acceptance

Let real child time expire, obtain a replacement through kiosk, unlock normally and observe the declared same usable activity or closed blocked app. Compare only earlier public observations; no claim about unseen events under lock.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_replacement`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
