# 037a — Save to a selected location through the installed chooser

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FILE03 installed feedback save; actual provider binding**. First scheduled consumer: [E2E-031, case 155](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **037** — FILE03 installed feedback open/cancel; actual provider binding.
- **031a** — FEED09 collection trace.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend FILE03 for the actual Gtk.FileDialog save chooser reached from feedback Download after public collection completion. Resolve and record its provider and caller independently of the Open binding; qualify this Save route even when the owner matches. Bind directory, filename, Save and closure; reject wrong modes and unknown overwrite dialogs. FEED08 owns opening and reading the resulting archive.

## Live VM acceptance

On the live VM, observe collection complete, open Download's chooser, choose a synthetic destination and filename, then Save. Independently observe closure and the named file in the file manager. Exercise Cancel from a fresh chooser and prove that no second file was created.

Record exactly the provider route and caller exercised. Refuse wrong ownership, ambiguous filename/directory and uncertain Save. A native result cannot qualify a portal binding or conversely; unsupported unused backends remain unqualified rather than adding speculative fixtures.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_save_chooser
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
Check **037a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
