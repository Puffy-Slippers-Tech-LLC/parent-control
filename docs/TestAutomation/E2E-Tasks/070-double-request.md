# 070 — Double-click kiosk Request and observe one prompt

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-014/kiosk (41–43). Scope: UI20 and REQUEST10's kiosk binding.

Required implemented capabilities: REQUEST01/03/04/05/09, AUTH02 and UI22. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement one deliberate native double-click gesture first. Surround it with UI22 prompt/form-count and Request availability traces; REQUEST10 also independently checks final counts. No input repair or internal exactly-once claim.

## Live VM acceptance

On the live kiosk, double-click an enabled Request once and observe one prompt plus the declared inhibition/count trace, then finish through the qualified agent. Disabled/hidden controls never receive the gesture. Overlay binding remains a separate slice.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_request_duration`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
