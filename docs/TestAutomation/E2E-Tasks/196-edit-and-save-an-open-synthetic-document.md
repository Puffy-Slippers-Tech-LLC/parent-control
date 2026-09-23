# 196 — Change a synthetic attachment source

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FILE09**. First scheduled consumer: [E2E-031, case 154](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend the shared FILE05 fixture helper to change only the declared synthetic source file over guarded SSH. Validate ownership, path and original content before one write; read back the changed file independently. The product feature under test is the attachment snapshot and re-add behavior.

Keep fixed fixture data and all file operations in shared infrastructure. Reject traversal, symlinks, wrong ownership and uncertain writes. For later retained-work consumers, compose the registered APP03/04 work fixture: make one observable edit/save and compare the same work after enforcement. Qualify that binding independently; source-file mutation alone cannot prove that a running app remains usable or retains its activity.

## Live VM acceptance

On the VM, change the declared synthetic source through the shared command and independently read the new bytes. Confirm refusal of wrong paths/owners and cleanup of only owned files. Case 154 owns the attachment snapshot and re-add assertions through the product UI.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_edit_and_save_an_open_synthetic_document
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
Check **196** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
