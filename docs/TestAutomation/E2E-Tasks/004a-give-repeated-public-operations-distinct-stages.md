# 004a — Give repeated public operations distinct stages

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **JourneyPlan repeated invocation IDs and assertion placement**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Required tasks: none (Baseline). Use the existing qualified source interfaces
and guarded attempt envelope; unqualified provider bindings remain unavailable.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend the existing JourneyPlan/worker exchange for finite repeated invocations and declared assertion boundaries. Keep fresh observations, durable storage before acknowledgement, ordered phases and the terminal failure latch. Do not change authentication in this slice.

## Live VM acceptance

In one guarded installed VM attempt, open Parent, switch between its two pages twice, and compare each return with its own earlier immutable settings observation. Require distinct stages and correctly placed assertions. Isolated recorder regressions must reject duplicate, missing, stale and reordered replies before live qualification.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_give_repeated_public_operations_distinct_stages
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **004a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
