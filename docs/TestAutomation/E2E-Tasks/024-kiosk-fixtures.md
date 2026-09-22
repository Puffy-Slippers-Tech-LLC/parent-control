# 024 — Prepare the no-approver kiosk profile

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add only the no-approver profile and its independent live empty-state result. Reuse 024b's fixture ownership/cleanup mechanics; both profiles remain part of the cumulative FIX03 contract.

Tasks **024b** supply the extracted operations through their maintained
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

Deliver **FIX03 no-child/no-approver profiles**. First scheduled consumer: [E2E-017, case 55](../E2E-Scenario-Recipes.md#e2e-017).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **012** — REQUEST04 kiosk child/approver; REQUEST08 unavailable state.
- **024b** — FIX03 no-child profile and public station empty state.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend the existing account fixture only for no-child and no-approver profiles, preserving fixed identities, the request station, ownership and outer cleanup. Reuse applicable FIX02 mechanics without turning it into arbitrary mutation. No approval prompt or product-policy mutation is needed.

## Live VM acceptance

In separate guarded VM attempts, enter the station for each empty profile and observe the exact empty choice set, unavailable explanation and disabled Request with no prompt. Pass identity/cleanup refusal regressions first. Multiple/ineligible-approver profiles remain pending.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_kiosk_fixtures
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
Check **024** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
