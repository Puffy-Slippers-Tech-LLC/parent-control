# 014 — Compose prepared request choices

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-015 kiosk cancel/escape (47, 48). Scope: FLOW04.

Required implemented capabilities: REQUEST04, REQUEST05, REQUEST06, REQUEST08; REQUEST11, REQUEST12. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose kiosk REQUEST01 → REQUEST03/04/05/06/08 in the documented order with explicit child, approver, duration and app choice. Receive an independently prepared enabled target; the composite does not change Parent policy.

## Live VM acceptance

On the live VM, enable the target through Parent with UI17/PARENT08 and use DESK03 to reach GDM. In the station, prepare a request, read back all chosen values and estimate, then exit normally. Re-enter from an independent GDM state and reproduce the result with fresh stage IDs.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_request_exit`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
