# 185p — Read Parent Help and legal notices and complete information links

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **INFO01 Parent**. First scheduled consumer: [E2E-042, case 190](../E2E-Scenario-Recipes.md#e2e-042).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **044a** — DESK10 same-desktop window switching.
- **185w** — INFO01 Parent website browser identity and close/return.
- **185v** — INFO01 Parent privacy page identity and close/return.
- **185s** — INFO01 Parent support mail recipient/subject and close without sending.
- **185l** — ABOUT02/03 actual license handler identity/content and close/return.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the separately qualified website, privacy, support and license handlers from tasks 185w, 185v, 185s and 185l. Qualify the owned Help/About entry and the remaining Legal notices destination through its actual document handler, then compose INFO01 Parent from those completed leaves. Keep exact public destination identity/content, normal close/return and Parent state comparison.

## Live VM acceptance

In installed Parent, capture selected child/settings, open Help/About and follow Legal notices. Read the actual notice document, close normally and compare the same Parent state. Independently supplied valid entry and wrong-document/handler/ambiguous-window refusals must pass. Retain each other destination's valid qualified result; the complete case 190 follows all offered links. No mail is submitted, and an inaccessible required destination leaves this task incomplete.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_read_parent_information_links
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
Check **185p** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
