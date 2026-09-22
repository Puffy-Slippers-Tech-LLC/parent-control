# 188p — Observe failed Parent diagnostic collection

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FEED09 Parent collection failure and usable controls**. First scheduled consumer: [E2E-046, case 209](../E2E-Scenario-Recipes.md#e2e-046).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** No deterministic public collection-failure trigger is established. Leave pending until an exact normal customer trigger is qualified; no internal fault injection. Recovery is required only by the separate Retry slice.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **031a** — FEED09 collection trace.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind FEED09's unavailable/partial collection explanation and editing/Close controls on Parent. Arm the public observer before entry. Enter ordinary feedback with FEED01. Record the exact genuine public prerequisite failure; a lost Internet connection alone does not fail local collection.

## Live VM acceptance

On the VM, observe collection actually fail on Parent with its read-only trace already active. Read the failure explanation, enter a synthetic draft through the usable editor and close normally through the usable Close action. No successful recovery or submission is needed to qualify this failure-state slice.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_parent_collection_failure
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
Check **188p** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
