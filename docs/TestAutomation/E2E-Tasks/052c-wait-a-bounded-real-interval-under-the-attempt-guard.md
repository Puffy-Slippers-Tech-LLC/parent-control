# 052c — Wait a bounded real interval under the attempt guard

Estimate: 15–30 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **TIME03**. First scheduled consumer: [E2E-032, case 156](../E2E-Scenario-Recipes.md#e2e-032).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Use the existing qualified source interfaces and guarded attempt envelope; no new capability prerequisite.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extract the existing guarded monotonic wait into TIME03 with an explicit duration, deadline and finite progress checkpoints. It returns elapsed time only and makes no product-state claim.

## Live VM acceptance

On the installed VM, read an already opened About window, wait five real seconds with the guard active, and independently read that same public window again. Isolated safety checks must stop the wait on lost ownership or deadline. No guest clock modification or simulated usage.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_wait_a_bounded_real_interval_under_the_attempt_guard
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
