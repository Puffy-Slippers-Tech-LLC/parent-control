# 048b — Complete overlay exits and approval compositions

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add immediate approved exit to the same activity, then compose overlay FLOW05/07. Reuse 048f's rejection/Cancel and 048d's automatic return.

Tasks **048f** supply the extracted operations through their maintained
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

Deliver **Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07**. First scheduled consumer: [E2E-015, case 46](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **021** — FLOW05/06/07 kiosk.
- **048c** — Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result.
- **048d** — AUTH02 overlay approval; REQUEST11/12 success and automatic child return.
- **048f** — AUTH02 overlay rejection/Cancel and preserved-form readback.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse task 048c's Shell recipient/Cancel binding and task 048d's sealed submission, approval and automatic child return. Add explicit wrong-password rejection and normal Cancel with preserved choices, then qualify immediate approved exit independently. Compose the overlay FLOW05/07 and complete result set only after those leaves pass; MATE proofs never authorize Shell input.

## Live VM acceptance

In separate live overlay attempts, enter one declared wrong password and observe explicit rejection, Cancel and compare the usable unchanged form; separately Cancel a fresh challenge. Approve another declared request and take the offered immediate exit after reading success, returning to the same child activity. Keep valid automatic-return evidence from 048d and rerun it when changed code affects it. Refuse wrong provider/request, stale or reused proof and uncertain delivery; require sealed capture, collection and cleanup.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_overlay_approval
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
Check **048b** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
