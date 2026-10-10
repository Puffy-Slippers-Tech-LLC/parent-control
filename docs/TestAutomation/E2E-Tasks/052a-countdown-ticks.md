# 052a — Measure final-second countdown ticks

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add final-second remaining-time progression with its declared sample order and tolerances. Reuse 052d's minute-sampling machinery; no clock changes or backend usage reads.

Reuse the delivered scope of tasks **052d** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **TIME02 minute/final-second ticks**. First scheduled consumer: [E2E-008, case 22](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052d** — TIME02 minute-precision sampling.

## Implementation

Extend 052d's TIME02 sampling with final-second progression, using TIME01, guarded TIME03 intervals and explicit UI12 elapsed-time comparisons. Declare public precision and tolerances before execution. Read the supported countdown format as needed to compare time; a separate formatting matrix remains in child UI coverage. Keep elapsed time distinct from an enforcement result.

Use 052d's new immutable sample-comparison operation with exact final seconds;
`CountdownObservation` and the existing `check_countdown_balance` alone do not
implement this progression. Bind the transition/sample schedule in the fixed
qualification, preserving the original allowance/deadline if a window is missed.

Use bounded read-only sampling of distinct values with controller timestamps;
do not require a sample on every second or at an exact timer callback. Include
read latency and public precision in the elapsed comparison while still
requiring final-second progress. No fresh allowance or approval repairs a missed
window in the same attempt.

## Live VM acceptance

In a fresh guarded VM attempt, publicly establish short daily-only time, enter the child and independently compare successive final-second values with real measured intervals. Include a minute-precision sample only when needed to establish the transition into the new branch. Require the declared sample order and tolerances, independent valid entry and stale/reversed/wrong-owner sample refusal. Reuse 052d's unchanged exact minute-progression qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state. No guest clock adjustment or usage probe is allowed.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_countdown_ticks
```
