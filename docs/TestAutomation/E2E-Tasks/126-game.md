# 126 — Prepare and play a real offline game windowed

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-023/windowed (126). Scope: the real game's APP01/02/03/04 bindings, APP05 and FLOW10 in windowed mode.

Required implemented capabilities: TIME04 and FLOW13's grant-only profile. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Pin a real offline game/level through FIX04 with meaningful public locators. Qualify APP05 windowed mode/level and actual gameplay, then FLOW10. Use real normal input and bounded public results; no fake game, timer or private state probe.

## Live VM acceptance

On the VM actually play the declared real windowed level, observe input effects and a recognizable activity, then play a short grant to natural lock. Missing public locators remain a named prerequisite.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_game`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
