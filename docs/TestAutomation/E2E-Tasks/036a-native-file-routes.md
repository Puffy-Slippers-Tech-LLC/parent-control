# 036a — Observe policy results for Files launches

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add this route's Hard/Soft denial and expected prior-window closure. Reuse 036f's usable/new-window Files route; no substitute launch path.

Tasks **036f** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **APP01/02/03 native file-manager route**. First scheduled consumer: [E2E-019, case 74](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE07/04/05; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **036f** — APP01/02/03 native file-manager usable/new-window route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the file manager's offered launch action to the declared native fixture and independently observe its usable or blocked result. Register a supported separate-window launch for later retained-activity comparisons. Reuse the prepared standard fixture; special-path and AppImage copying stay with their own consumers.

## Live VM acceptance

On the live VM, launch the declared native fixture from the file manager and perform a normal action with a visible result. Open a distinguishable new window beside an earlier activity. Save Hard and Soft rules in Parent, then require this route's declared denied result and expected window closure. No alternative route substitutes for this action.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_native_file_routes
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
Check **036a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
