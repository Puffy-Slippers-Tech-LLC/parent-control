# 024 — Prepare empty kiosk account profiles

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-017/no-child and no-parent (54, 55). Scope: FIX03's two empty-choice profiles.

Required implemented capabilities: REQUEST01/03 kiosk entry/readback, REQUEST04 child/approver selectors and REQUEST08's unavailable-state readback. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Extend the existing account fixture only for no-child and no-approver profiles, preserving fixed identities, the request station, ownership and outer cleanup. Reuse applicable FIX02 mechanics without turning it into arbitrary mutation. No approval prompt or product-policy mutation is needed.

## Live VM acceptance

In separate guarded VM attempts, enter the station for each empty profile and observe the exact empty choice set, unavailable explanation and disabled Request with no prompt. Pass identity/cleanup refusal regressions first. Multiple/ineligible-approver profiles remain pending.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_kiosk_choices`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
