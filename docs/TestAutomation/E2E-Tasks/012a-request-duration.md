# 012a — Reject invalid kiosk durations

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add the invalid-custom REQUEST09 branch: validation with otherwise enabled Request, preserved form and no authentication. Reuse 012c's valid controls and estimate reader.

Tasks **012c** supply the extracted operations through their maintained
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

Deliver **REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk**. First scheduled consumer: [E2E-015, case 47](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **012** — REQUEST04 kiosk child/approver; REQUEST08 unavailable state.
- **009** — UI16.
- **012c** — REQUEST04/05/06/08 kiosk valid durations, estimates and app choice.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind UI15 to duration choices, UI16 to custom input and UI17 to the soft-app
toggle before composing the request blocks. Read choices and the public estimate
independently. Reuse shared form observations; mute remains a gated extension.

## Live VM acceptance

In a fresh installed VM attempt, enable the declared child through Parent,
observe saving, then Switch User to enter kiosk and select that child/approver.
Select a preset, a valid fraction and Rest of the day; observe each selection
and estimate with explicit elapsed-time bounds. Change the soft-app choice and
read it back. Invalid custom input shows validation while an otherwise ready
Request remains enabled. Selecting it keeps the same form open and starts no
authentication prompt. Do not change the clock or submit authentication.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_request_duration
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
Check **012a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
