# 077a — Read app rows and initial access choices

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **PARENT12; UI13 complete public app-row observations**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and the selected consumer's recipe.

Required tasks: none (Baseline). Use the existing qualified source interfaces
and guarded attempt envelope; unqualified provider bindings remain unavailable.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Register bounded app-row identity, access and match projections using UI01/02/03, then a complete UI13 row-set read. Use ordinary App Limits navigation and public scrolling when required. Return immutable semantic values; the caller supplies expected choices. Reuse installed baseline apps without adding native launch fixtures.

## Live VM acceptance

On a fresh installed VM, open Parent for the child, visit App Limits and read the declared app rows and their default Allowed choices. Require a complete bounded row set before asserting no blocks; an inaccessible or stale traversal cannot prove absence. Re-read from an independently opened App Limits page, and refuse a wrong child/page. No app-policy edits or launches are required.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_app_row_observations
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
Check **077a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
