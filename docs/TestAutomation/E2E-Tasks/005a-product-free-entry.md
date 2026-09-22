# 005a — Start a graphical journey before product installation

Estimate: 30–50 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: Product-free setup changes shared preparation and ownership handling; its live entry and affected retained regressions must finish together.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **Product-free graphical start and verified package staging**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001t** — FILE01/02/06 terminal command, help/denial projections and normal close/return.
- **004** — UI19/GDM05 distinct single-use authentication challenges.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the accepted product-free baseline and FIX04 transfer. Extend the existing declared setup mode so this journey starts without InstalledSetup installing or rebooting the product. Retain input digests, ownership, capture sealing, phase timing and cleanup. Qualify GDM07 and FILE01 on that baseline; no product installation happens in this slice.

## Live VM acceptance

Start a fresh guarded VM attempt from the accepted product-free baseline, authenticate the intended administrator through two fresh recipient proofs, launch Terminal and observe its usable nonsecret input. Verify the setup-mode/ownership refusals in isolated regressions before the live run. Do not use a maintenance reset as a customer step.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_product_free_entry
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
Check **005a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
