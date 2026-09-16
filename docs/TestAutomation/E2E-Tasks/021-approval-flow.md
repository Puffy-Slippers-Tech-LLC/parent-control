# 021 — Compose approval, kiosk time and rejection

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-016 requests (50–52). Scope: FLOW05, FLOW06, FLOW07.

Required implemented capabilities: AUTH02; FLOW04. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement FLOW05 first from REQUEST09/AUTH02/REQUEST11/REQUEST12, then FLOW06 from kiosk FLOW04/FLOW05, and FLOW07 for reject/cancel without retry. Bind fresh stages for every invocation and observe automatic kiosk exit.

## Live VM acceptance

On the VM, obtain real short time through the station and return to GDM. In separate attempts reject/cancel, compare preserved choices, then approve with a new challenge. FLOW07 must finish with the form open.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_station`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
