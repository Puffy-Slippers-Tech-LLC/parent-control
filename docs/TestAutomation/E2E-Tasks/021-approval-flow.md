# 021 — Compose kiosk rejection and cancellation

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Compose FLOW07 rejection/Cancel with preserved form and a later deliberately new challenge. Reuse 021a for successful approval/time composition.

Tasks **021a** supply the extracted operations through their maintained
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

Deliver **FLOW05/06/07 kiosk**. First scheduled consumer: [E2E-016, case 51](../E2E-Scenario-Recipes.md#e2e-016).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **020** — AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits.
- **014** — FLOW04 kiosk.
- **021a** — FLOW05/06 kiosk approved branch.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement FLOW05 first from REQUEST09/AUTH02/REQUEST11/REQUEST12, then FLOW06 from kiosk FLOW04/FLOW05, and FLOW07 for reject/cancel without retry. Bind fresh stages for every invocation and observe automatic kiosk exit.

## Live VM acceptance

On the VM, obtain real short time through the station and return to GDM. In separate attempts reject/cancel, compare preserved choices, then approve with a new challenge. FLOW07 must finish with the form open.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_approval_flow
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
Check **021** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
