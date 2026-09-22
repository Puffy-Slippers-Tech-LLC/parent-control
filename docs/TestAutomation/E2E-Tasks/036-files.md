# 036 — Qualify file rename and compose synthetic-file operations

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FILE07/04/05; FIX04 synthetic files**. First scheduled consumer: [E2E-031, case 152](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **009** — UI16.
- **036d** — FILE05 copy; exact source/destination and public resulting entry.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse task 036c's staged synthetic files and Nautilus Location/entry projections, and task 036d's public copy operation. Add normal Rename for one exact synthetic file, then compose the existing navigation/copy/rename contract. Keep dynamic names inside the scoped Files adapter; direct filesystem changes cannot supply acceptance.

## Live VM acceptance

On the VM open the normal file manager, navigate to the synthetic directory, select the exact file, copy and rename through normal UI, and observe the expected entries independently. Supply an independently opened file manager as another entry; wrong/absent destinations refuse without fallback.

For Rename independently observe the new entry and absence of the old entry in a complete recognized directory. Exercise Cancel and wrong-file/duplicate-name refusal. Retain source/destination guards and never replay an uncertain copy or rename.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_files
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
Check **036** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
