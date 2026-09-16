# 010 — Set one public toggle explicitly

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-017/disabled-child (57); E2E-005. Scope: UI17.

Required implemented capabilities: Existing qualified primitives and attempt envelope only. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement read-before-input, a single activation only when different, and a fresh state read. Register Parent Screen time limit; further toggle bindings are qualified with their consumer.

## Live VM acceptance

On installed Parent, enable and disable Screen time limit, then request its already-current state and observe no extra activation. Disabled settings remain readable; wrong/hidden controls refuse.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_kiosk_choices`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
