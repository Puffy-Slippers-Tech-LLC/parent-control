# 141 — Qualify product removal and reinstall commands

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation**. First scheduled consumer: [E2E-027, case 139](../E2E-Scenario-Recipes.md#e2e-027).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **007** — LIFE02.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **014** — FLOW04 kiosk.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the exact verified remove and reinstall commands, permitted prompts and
completion/reboot notices. Compose the corresponding LIFE05 notice/reboot path from the qualified LIFE02/GDM07 operations, and keep mechanical file,
account and migration checks under their existing system owners. Purge and
fresh-default observation are a separate capability.

## Live VM acceptance

On the live VM, remove the product through the administrator terminal, read the final reboot-required text, reboot normally and enter the child desktop to use the prepared app. Reinstall, follow the actual activation notice and open Parent. Require affected package cleanup checks and owned cleanup; case 139 owns the complete retained-settings lifecycle.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_product_removal
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
Check **141** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
