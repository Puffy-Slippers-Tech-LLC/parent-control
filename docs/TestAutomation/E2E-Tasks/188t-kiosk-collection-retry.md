# 188t — Retry failed kiosk diagnostic collection

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED16 kiosk collection recovery**. First scheduled consumer: [E2E-046, case 212](../E2E-Scenario-Recipes.md#e2e-046).
Read the [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and the selected consumer's recipe.

**Gate:** The genuine public failure and its normal recovery must both be available. Keep this slice pending if recovery is unavailable; the failure-state slice remains independently qualified.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **188k** — FEED09 kiosk collection failure and usable controls; gate in brief.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose FEED16 from the independently supplied failed-collection observation, one normal Retry collection input, FEED09 ready-state readback and FEED03/UI12 draft comparison. Reuse the qualified kiosk entry and failure projections.

## Live VM acceptance

In a fresh live attempt, reproduce the qualified kiosk collection failure, enter a synthetic draft, restore the declared public prerequisite and select Retry once. Require completed collection and the unchanged draft, then close normally. An already-ready draft cannot stand in for failure-before-recovery.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_kiosk_collection_retry
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
