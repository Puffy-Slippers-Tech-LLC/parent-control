# 132 — Compose a daily-dominant profile without clearing the grant

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW13 daily-dominant scope**. First scheduled consumer: [E2E-024, case 128](../E2E-Scenario-Recipes.md#e2e-024).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.

## Implementation

Extend FLOW13 with real short grant at daily=0, then increase daily allowance while Screen time limit stays enabled. Supply earlier observations and verify D>G>0 at both Parent and the later request estimate.

## Live VM acceptance

On the live VM preserve a real G while raising D through Parent, then read D>G>0 again at request time with elapsed/rounding margins. A reversed inequality fails; never relabel the variant.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_time_profiles_dominant
```
