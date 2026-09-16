# 011 — Enter and read the request station

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-017 account availability; E2E-015 kiosk exits. Scope: REQUEST01, REQUEST03.

Required implemented capabilities: Existing qualified primitives and attempt envelope only. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Qualify the public kiosk bus and GDM02 passwordless station route, plus UI15 session choice only if offered. Implement station entry and shared immutable form observations; fixed overlay-child binding is qualified later.

## Live VM acceptance

From live GDM enter the dedicated station through its offered session control, observe one request form and exact public child/approver/duration/control state. Prove unavailable selectors without activating them. No desktop-login shortcut.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_kiosk_choices`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
