# 166 — Suspend and wake through normal controls

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-022/suspend-wake (124, 125). Scope: LIFE03.

Required implemented capabilities: TIME01, TIME02, TIME03; DESK02, DESK03, DESK04; DESK08, DESK11. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose system controls, guarded real wait, supported wake input and observed actual return surface. Keep subsequent unlock separate; retained activity comparisons require successful legitimate access.

## Live VM acceptance

On the VM suspend normally, wait the declared real interval, wake through supported input and observe lock/desktop, then use DESK08 as applicable. Validate both positive-time access and elapsed-time denial through public results.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_suspend`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
