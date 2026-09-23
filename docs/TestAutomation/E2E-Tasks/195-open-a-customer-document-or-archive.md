# 195 — Qualify archive contents and compose document opening

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FILE08**. First scheduled consumer: [E2E-031, case 154](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **195a** — FILE08 text-document identity/content and normal close/return.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse task 195a's text-document Open/read/close binding. Add the actual File Roller archive route: exact archive identity, declared entry, its content handler, meaningful public content and normal close/return. Resolve archive and entry separately inside the provider adapter. Compose FILE08 only after the document and archive leaves are qualified; no extraction or PDF reader is required by this consumer.

## Live VM acceptance

On the VM, open each staged synthetic file through its normal handler and read the identifying public contents/window. Use shared direct handler launch and qualify an independently opened document; a missing file or unexpected handler fails without a fallback launch.

For the archive, read its identifying public entry/content and close normally to the expected surrounding Files surface. Refuse wrong archive/entry, ambiguous handler, unrelated content and uncertain close. A window title alone cannot identify the document.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_open_a_customer_document_or_archive
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
Check **195** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
