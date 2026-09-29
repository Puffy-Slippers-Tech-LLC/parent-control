# 185p — Check Parent Help/About information links

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
- **185w** — INFO01 Parent website link clickability.
- **185v** — INFO01 Parent privacy link clickability.
- **185s** — INFO01 Parent support link clickability.
- **185l** — Retained ABOUT02/03 entry/return helpers; use the current link-only contract.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Complete the Parent UI matrix for owned Help/About information and clickable
link controls using the shared readers. Installed acceptance
below owns link clickability and unchanged product state, without
repeating layout/scale/content permutations.

Reuse the website, privacy and support readers from tasks 185w, 185v and 185s.
Check Help, License and Legal notices are clickable through the same shared
reader, then compose INFO01 Parent. Stop at visible/enabled state and a usable
public activation action; do not activate links or inspect their URIs or
destinations. Keep owned About close and Parent state comparison.

## Live VM acceptance

In installed Parent, capture selected child/settings, check Help and the
License/Legal notices controls are clickable without invoking them, close
About and compare the same Parent state. Independent entry and
missing/disabled/nonactionable/wrong-owner refusals must pass. Retain each
other link's qualified clickability result; complete case 190 checks all
offered links. Browser, mail and document handlers are not prerequisites.

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
