# 020 — Qualify immediate approved kiosk exit

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add the immediate approved exit to GDM and compose the full kiosk outcome set. Reuse 020b's rejection/Cancel and 020a's automatic-exit evidence; rerun any affected branch.

Task **020b** supplies the extracted operations through its maintained
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

Deliver **AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits**. First scheduled consumer: [E2E-016, case 50](../E2E-Scenario-Recipes.md#e2e-016).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **019** — REQUEST09, AUTH01 kiosk.
- **013** — REQUEST11/12 kiosk Cancel and Escape.
- **020a** — AUTH02 kiosk approval; REQUEST11/12 success and automatic GDM exit.
- **020b** — AUTH02 kiosk rejection/Cancel with REQUEST11 preserved-form results.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

Start at `kiosk_approval.PLAN`, `AccessibleUI.kiosk_mate_approval` /
`kiosk_approval_success`, and `onpc_request_flow::run(exchange, 'approval')`.
Reuse `kiosk_rejection.PLAN` / `KioskRejectionJourney`,
`AccessibleUI.kiosk_mate_rejected` and
`onpc_request_flow::run(exchange, 'rejection')` for affected rejection branches.
The rejection/Cancel evidence is report run `20260926T154532Z-4ed66f34`, with
collection, owned cleanup and baseline restoration passed. Supporting checks
are `test_e2e_kiosk_valid_duration.py`, `test_challenges_cleanup_safety.py` and
`test_installed_journey_cleanup_safety.py`.

## Implementation

Reuse task 020a's qualified MATE submission and automatic approved exit and
020b's explicit rejection/Cancel and independent preserved-form readback.
Qualify the offered immediate exit after a correct approval in its own attempt.
Compose the complete AUTH02 and REQUEST11/12 result set only after these leaves
pass; do not require this composite before its adapters.

## Live VM acceptance

Retain 020b's separate fresh-entry wrong-password rejection/Cancel and
password-free Cancel evidence; rerun either branch if affected by changes.
Approve with correct credentials in a new attempt, read success and take the
offered immediate exit to independently observed GDM. Retain the valid
automatic-exit qualification from 020a; rerun it when changed code affects that
route. Timeout is not rejection, and authentication disappearance is not
approval. Require sealed capture reconciliation and cleanup for every outcome.

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
