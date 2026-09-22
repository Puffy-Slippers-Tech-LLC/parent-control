# 037 — Select multiple files or cancel through the installed chooser

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FILE03 installed feedback open/cancel; actual provider binding**. First scheduled consumer: [E2E-031, case 152](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE07/04/05; FIX04 synthetic files.
- **029** — FEED01, FEED03.
- **031** — FEED09 validation/control snapshots.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the actual chooser reached from installed feedback's Gtk.FileDialog Add files action. Record whether that caller uses the native GTK or portal/Nautilus provider and implement that scoped binding, with its real owner/dialog/caller relationship. Use available Builder IDs and provider-local semantics for dynamic entries. Include the owned Add files invocation and exact attachment-list readback leaves; task 038 owns the remaining attachment behavior. Navigate, read the exact multi-selection, Open once and observe closure and caller result. Preserve modifiers so the second selection cannot silently drop the first.

## Live VM acceptance

In installed feedback, select two synthetic files and observe the exact set before Open. Require chooser closure, then independently compare the displayed attachment list. Reopen and Cancel with a different candidate selected; the prior attachment list must stay unchanged.

Require the actual caller/dialog ownership proof, wrong-dialog/mode and partial-selection refusal, independent valid entry, and no replay after uncertain input. Record exactly the provider route exercised. Native and portal evidence are distinct; this customer recipe does not require inventing another caller or forcing an unused backend. Any other route remains unqualified in the catalogue.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_file_chooser
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
Check **037** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
