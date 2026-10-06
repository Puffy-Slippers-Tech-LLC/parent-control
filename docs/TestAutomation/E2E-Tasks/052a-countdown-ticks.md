# 052a — Measure final-second countdown ticks

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add final-second formatting/ticks with their declared sample order and tolerances. Reuse 052d's minute-sampling machinery; no clock changes or backend usage reads.

Reuse the delivered scope of tasks **052d** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **TIME02 minute/final-second ticks**. First scheduled consumer: [E2E-008, case 21](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — TIME01 child-desktop presence and limits-off absence.
- **051** — FLOW13 daily-only, fresh/same Parent entry with observed G=0.
- **052c** — TIME03.
- **052d** — TIME02 minute-precision sampling.

## Implementation

Compose TIME02 from TIME01, guarded TIME03 intervals and explicit UI12 elapsed-time comparisons. Declare public precision, formatting and tolerances before execution. Keep elapsed time distinct from an enforcement result.

## Live VM acceptance

On the live VM, publicly establish short daily-only time, enter the child and observe minute ticks and final-second changes over real measured intervals. Require the declared sample order and tolerances. No guest clock adjustment or usage probe is allowed.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_countdown_ticks
```
