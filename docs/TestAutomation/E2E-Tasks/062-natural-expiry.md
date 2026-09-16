# 062 — Use an app until a natural enforced lock

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-008/retained-unlock (21). Scope: TIME04.

Required implemented capabilities: TIME01, TIME02, TIME03; FLOW13's daily-only profile; APP03/04 and FLOW08's native usable-app branch. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose bounded APP03 actions/TIME03 waits, TIME02 only while visible, and public lock/input-ownership observations. Receive earlier visible balance and deadline explicitly.

## Live VM acceptance

From daily-only time prepared through customer controls, use the actual app until natural exhaustion. Observe lock and a harmless key reaching the lock challenge while desktop interaction is unavailable. No manual Lock, backend expiry, or hidden-window inspection.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_expiry`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
