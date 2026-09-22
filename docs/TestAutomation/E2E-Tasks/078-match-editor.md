# 078 — Validate and reset one match rule

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add local invalid drafts and immediate Reset-to-default save. Reuse 078a's editor/Save/Cancel; broker-rejected reports remain task 186.

Tasks **078a** supply the extracted operations through their maintained
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

Deliver **PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts**. First scheduled consumer: [E2E-045, case 205](../E2E-Scenario-Recipes.md#e2e-045).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **077** — PARENT10, PARENT11.
- **017** — PARENT08 snapshot saved/control states; installed qualification and owned cleanup passed.
- **078a** — PARENT13/15 match editor, valid Save and Cancel.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement PARENT13 first, then PARENT15 Save, Cancel, Reset and local invalid-draft results. Compare Cancel with the supplied old rule and Reset with its immediate default save. Broker-rejected wildcard reporting is qualified separately with FEED15.

## Live VM acceptance

In installed Parent, enter a valid same-directory wildcard, Cancel and read the old rule; reopen, Save and read the new rule. Empty/unrelated precise input must leave the editor open with validation. Reset saves the detected default immediately. Bind inputs before execution and use no preference reads.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_match_editor
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
Check **078** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
