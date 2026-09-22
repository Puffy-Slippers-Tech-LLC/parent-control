# 141a — Qualify purge and reinstall to visible defaults

Estimate: 30–50 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: Purge, actual activation, usable child access and reinstall-to-defaults must be observed in one fresh qualification.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **LIFE04 purge; LIFE05 notice and reinstall/defaults**. First scheduled consumer: [E2E-027, case 139](../E2E-Scenario-Recipes.md#e2e-027).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **141** — LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the exact verified purge command, permitted challenge and final notice. After ordinary activation, use the qualified install route again before inspecting fresh defaults. Keep file/account cleanup assertions in existing mechanical tests.

## Live VM acceptance

In a fresh live attempt, make one public setting nondefault, purge through the administrator terminal and follow its actual activation notice. Enter an ordinary child desktop and use the fixture app. Reinstall, follow activation and read the visible fresh default before editing. Require package cleanup checks and owned cleanup; the uninterrupted retained-settings journey remains case 139.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_product_purge
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
Check **141a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
