# 045 — Save and open customer-selected diagnostics

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FEED08**. First scheduled consumer: [E2E-031, case 155](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **037a** — FILE03 installed feedback save; actual provider binding.
- **044a** — DESK10 same-desktop window switching.
- **195** — FILE08.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the real Download, Save chooser, file-manager navigation and actual viewer. Register bounded expected public export headings and the viewer/feedback DESK10 bindings, without opening source product logs or collector internals.

Use task 037a's recorded Save binding for the actual caller and the qualified File Roller/archive-entry and text-handler routes. The current export consumer reads ZIP/text contents; it has no PDF-viewer prerequisite. Keep saved-document identity and normal close/return distinct from source log inspection.

## Live VM acceptance

On the VM observe diagnostic collection, save output to the selected directory, open it through the file manager and read the expected public headings. Return to the still-open feedback dialog without editing its draft.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_diagnostic_export
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
Check **045** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
