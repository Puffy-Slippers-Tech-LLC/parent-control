# 028 — Close and reopen Parent

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **LIFE01**. First scheduled consumer: [E2E-035, case 158](../E2E-Scenario-Recipes.md#e2e-035).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks: none (Baseline). Use the existing qualified source interfaces
and guarded attempt envelope; unqualified provider bindings remain unavailable.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose UI18 and shared PARENT01 for normal Parent closure/relaunch. LIFE01 observes the new window without selecting a child or restoring fields. Keep explicit prior-window and destination arguments.

## Live VM acceptance

Open Parent on the VM, close it normally, prove it disappeared, relaunch through PARENT01's direct command and observe the new management window. Read its initial selection before any edit; an already-closed/wrong window must not trigger repair.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_app_restart
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
Check **028** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
