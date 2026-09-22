# 020 — Qualify kiosk rejection, Cancel and immediate approved exit

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits**. First scheduled consumer: [E2E-016, case 50](../E2E-Scenario-Recipes.md#e2e-016).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **019** — REQUEST09, AUTH01 kiosk.
- **013** — REQUEST11/12 kiosk Cancel and Escape.
- **020a** — AUTH02 kiosk approval; REQUEST11/12 success and automatic GDM exit.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse task 020a's qualified MATE submission and automatic approved exit. Add the explicit wrong-password/rejection observation, normal Cancel and independent preserved-form readback. Qualify the offered immediate exit after a correct approval in its own attempt. Compose the complete AUTH02 and REQUEST11/12 result set only after these leaves pass; do not require this composite before its adapters.

## Live VM acceptance

In separate fresh live attempts, submit one declared wrong fixture password and observe explicit rejection, then Cancel normally and verify unchanged choices; separately Cancel a fresh challenge without password submission. Approve with correct credentials in another attempt, read success and take the offered immediate exit to independently observed GDM. Retain the valid automatic-exit qualification from 020a; rerun it when changed code affects that route. Timeout is not rejection, and authentication disappearance is not approval. Require sealed capture reconciliation and cleanup for every outcome.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_auth_result
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
Check **020** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
