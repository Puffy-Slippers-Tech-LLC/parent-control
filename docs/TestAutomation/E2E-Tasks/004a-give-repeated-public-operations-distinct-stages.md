# 004a — Give repeated public operations distinct stages

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **JourneyPlan repeated invocation IDs and assertion placement**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Use the existing qualified source interfaces and guarded attempt envelope; no new capability prerequisite.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend the existing JourneyPlan/worker exchange for finite repeated invocations and declared assertion boundaries. Keep fresh observations, durable storage before acknowledgement, ordered phases and the terminal failure latch. Do not change authentication in this slice.

## Live VM acceptance

In one guarded installed VM attempt, open Parent, switch between its two pages twice, and compare each return with its own earlier immutable settings observation. Require distinct stages and correctly placed assertions. Isolated recorder regressions must reject duplicate, missing, stale and reordered replies before live qualification.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_give_repeated_public_operations_distinct_stages
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
