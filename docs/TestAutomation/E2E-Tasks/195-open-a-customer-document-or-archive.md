# 195 — Inspect declared ZIP artifacts through guarded SSH

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FILE08 bounded ZIP entry/content reads over SSH**. First scheduled consumer: [E2E-031, case 155](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **195a** — FILE08 bounded text-artifact identity/content reads over SSH.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse task 195a's guarded artifact identity and bounded content comparisons.
Add a fixed ZIP inspection operation using a maintained public archive API in
the shared SSH helper. Enumerate the exact member set, including empty directory
entries, and read only declared text/JSON members with explicit archive, member,
expanded-byte and time limits. Reject malformed archives, duplicate/unsafe member
names and replacement. Read members without extracting or launching Files,
File Roller or an editor. Observe actual bytes independently of the product's
export implementation; neither fixture expectations nor command success prove
the archive's contents. Source product logs and collector internals stay outside
this reader's allowed paths.

## Live VM acceptance

On the VM, inspect the declared synthetic ZIP through guarded SSH and compare
its exact entries, empty folders and bounded text/JSON contents. Repeat with an
independently prepared valid archive. Qualify wrong archive/entry/owner,
replacement, malformed/duplicate entries and over-limit refusal. Require owned
cleanup and sanitized evidence. Task 045 binds these reads to a real product
Download/Save result; staged files alone cannot pass that export assertion.

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
