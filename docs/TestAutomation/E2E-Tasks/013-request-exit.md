# 013 — Observe request results and exits

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015 kiosk cancel/escape (47, 48). Scope: REQUEST11, REQUEST12.

Required implemented capabilities: REQUEST01, REQUEST03. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement named form results and exit routes using fresh observations. Start with kiosk Cancel/Escape and no active authentication prompt; approval, rejection and overlay destinations qualify with their consumers.

## Live VM acceptance

On the VM, enter kiosk and separately exit through Cancel and Escape; prove form disappearance plus usable GDM. Verify cancellation has no error. An active authentication dialog cannot be dismissed by guessing a form-exit route.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_request_exit`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
