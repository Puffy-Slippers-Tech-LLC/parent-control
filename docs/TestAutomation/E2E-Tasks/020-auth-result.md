# 020 — Approve, reject or cancel a fresh request challenge

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-016 and E2E-017. Scope: AUTH02.

Required implemented capabilities: REQUEST09, AUTH01; REQUEST11, REQUEST12. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose two fresh AUTH01 checks, UI19 and submit for correct/wrong credentials; cancellation uses its declared public control. Observe explicit acceptance/rejection/dismissal and extend REQUEST11 accordingly. Later attempts require new challenges.

## Live VM acceptance

Run separate live kiosk attempts for correct password, wrong password and Cancel. Read the resulting form message/choices, and observe brief success before automatic exit. Timeout is never authentication rejection; credentials remain private.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_station`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
