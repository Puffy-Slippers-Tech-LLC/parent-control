# 184b — Remove a logged-out spare child through Users

Estimate: 25–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **ACCOUNT02 remove-child**. First scheduled consumer: [E2E-040, case 180](../E2E-Scenario-Recipes.md#e2e-040).
Read the [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **184** — ACCOUNT02 add-child; AUTH04 account-creation password fields.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose only the normal remove action and its explicit confirmation for a registered spare child. Prepare that spare through the qualified add route in this attempt. Refuse an active child, the last administrator and the station before any removal input.

Resolve the actual Settings removal controls and confirmations within the declared spare account. Reject protected or ambiguous accounts before input. Read the resulting complete public list; account-database probes cannot replace it.

## Live VM acceptance

On the live VM, add a spare, keep it logged out, and select its removal in Users. Cancel first and observe the unchanged list; reopen, confirm and independently require only that spare absent. Parent/request refresh remains in the scenario consumers.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_remove_disposable_child
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
Check **184b** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
