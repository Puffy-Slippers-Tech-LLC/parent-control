# 007 — Observe a deliberate customer reboot

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-002 (2). Scope: LIFE02.

Required implemented capabilities: DESK02, DESK03, DESK04; LIFE04. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Add one explicitly planned customer boot transition to InstalledJourney, reusing the qualified product-free installation start. Reboot through desktop controls, bind the changed boot only as harness continuity, and reacquire fresh GDM. Unplanned reboot still fails. This task does not introduce another setup route.

## Live VM acceptance

In the same live installation attempt, perform the requested normal reboot, observe fresh usable GDM, sign in normally and reach the administrator desktop. No in-journey baseline restore or replacement adoption; run affected ownership/recorder safety checks.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_install`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
