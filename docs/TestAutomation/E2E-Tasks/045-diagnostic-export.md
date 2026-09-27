# 045 — Save diagnostics and inspect the exported artifact through SSH

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
- **195** — FILE08 bounded ZIP entry/content reads over SSH.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the real Download and task 037a's caller-bound Save chooser with FILE08's
shared read-only ZIP inspection over guarded SSH. Bind the exact newly saved
artifact, attempt and user before reading its declared entries, system information
and bounded contents. Preserve file identity through inspection and register
sanitized comparisons as evidence. No Files, archive-viewer or editor GUI is
needed. Do not open source product logs or collector internals, call the broker
export API in place of Download, or reuse a staged ZIP as the product result.

## Live VM acceptance

On the VM observe diagnostic collection, save output to the selected directory,
then independently inspect that exported file through FILE08 and compare the
expected public entries/headings and contents. Reobserve the still-open feedback
dialog and unchanged draft without editing. Command success alone cannot pass
the export assertion; no viewer window is required for the return check.

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
