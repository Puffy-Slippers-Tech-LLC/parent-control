# 028 — Close and reopen Parent

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/draft-reopen (152). Scope: LIFE01.

Required implemented capabilities: Existing qualified primitives and attempt envelope only. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Extend UI18 and SEARCH05 only for normal Parent closure/relaunch. LIFE01 observes the new window without selecting a child or restoring fields. Keep explicit prior-window and destination arguments.

## Live VM acceptance

Open Parent on the VM, close it normally, prove it disappeared, relaunch through the app grid and observe the new management window. Read its initial selection before any edit; an already-closed/wrong window must not trigger repair.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
