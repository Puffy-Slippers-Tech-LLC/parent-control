# 188r — Retry failed Parent diagnostic collection

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED16 Parent collection recovery**. First scheduled consumer: [E2E-046, case 208](../E2E-Scenario-Recipes.md#e2e-046).
Read the [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and the selected consumer's recipe.

**Gate:** The genuine public failure and its normal recovery must both be available. Keep this slice pending if recovery is unavailable; the failure-state slice remains independently qualified.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **188p** — FEED09 Parent collection failure and usable controls; gate in brief.
- **031a** — Parent's completed diagnostic-collection result after recovery.

## Implementation

Compose FEED16 from the independently supplied failed-collection observation, one normal Retry collection input, FEED09 ready-state readback and FEED03/UI12 draft comparison. Reuse the qualified Parent entry and failure projections.

Extend `feedback_collection.PLAN`, `AccessibleUI.wait_feedback_collection`
and the shared feedback API operation with `feedback-retry-logs`.
The failed-before-ready composition and its selector are planned; reuse the
unchanged ready-state observation without rerunning its two-entry history.

## Live VM acceptance

In a fresh live attempt, reproduce the qualified Parent collection failure, enter a synthetic draft, restore the declared public prerequisite and select Retry once. Require completed collection and the unchanged draft, then close normally. An already-ready draft cannot stand in for failure-before-recovery.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_parent_collection_retry
```
