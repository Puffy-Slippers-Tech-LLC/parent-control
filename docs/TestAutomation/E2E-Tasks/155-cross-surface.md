# 155 — Compare kiosk choices at each child overlay

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add kiosk-to-overlay for both children. Reuse 155a's comparisons; keep direction-specific approvers and no-approval scope.

Tasks **155a** supply the extracted operations through their maintained
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

Deliver **FLOW12 current choices**. First scheduled consumer: [E2E-018, case 60](../E2E-Scenario-Recipes.md#e2e-018).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.
- **155a** — FLOW12 overlay-to-kiosk choices for both children.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose FLOW12 in each direction from the declared request exit, entry and REQUEST03/UI12 comparisons. Duration, custom value and soft-app choice follow the child; the station and each overlay keep their own approver. Qualify both children and read the destination before editing. This composition performs no approval.

## Live VM acceptance

On the VM, publicly enable both children with ample time. Seed the recipe's different values and local approvers, then compare overlay→kiosk and kiosk→overlay before changing any selection. Each route must finish with the destination form open. Current mute absence has no interactive value; deferred mute does not block this task.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_cross_surface
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
Check **155** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
