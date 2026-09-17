# 188t — Retry failed kiosk diagnostic collection

Estimate: 25–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED16 kiosk collection recovery**. First scheduled consumer: [E2E-046, case 212](../E2E-Scenario-Recipes.md#e2e-046).
Read the [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and the selected consumer's recipe.

**Gate:** The genuine public failure and its normal recovery must both be available. Keep this slice pending if recovery is unavailable; the failure-state slice remains independently qualified.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **188k** — FEED09 kiosk collection failure and usable controls.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose FEED16 from the independently supplied failed-collection observation, one normal Retry collection input, FEED09 ready-state readback and FEED03/UI12 draft comparison. Reuse the qualified kiosk entry and failure projections.

## Live VM acceptance

In a fresh live attempt, reproduce the qualified kiosk collection failure, enter a synthetic draft, restore the declared public prerequisite and select Retry once. Require completed collection and the unchanged draft, then close normally. An already-ready draft cannot stand in for failure-before-recovery.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_kiosk_collection_retry
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
