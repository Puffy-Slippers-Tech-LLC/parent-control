# 012 — Read kiosk disabled-child availability

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add REQUEST08 disabled-child explanation and unavailable Request, reusing 012b's eligible selectors. Preserve the separate enabled and disabled preparations and no-prompt checks.

Tasks **012b** supply the extracted operations through their maintained
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

Deliver **REQUEST04 kiosk child/approver; REQUEST08 unavailable state**. First scheduled consumer: [E2E-017, case 57](../E2E-Scenario-Recipes.md#e2e-017).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **011** — REQUEST01, REQUEST03.
- **017** — PARENT08 snapshot saved/control states; installed qualification and owned cleanup passed.
- **003d** — DESK04 direct logout command and independent GDM result.
- **012b** — REQUEST04 kiosk eligible account choices and selected-value readback.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind UI15 to the offered child/approver selectors, then compose REQUEST04 with independent REQUEST03 readback. Read each exact eligible choice set before selection. Bind REQUEST08's unavailable explanation and distinguish disabled selectors from empty lists. Duration editing, numeric estimates and toggles remain pending.

## Live VM acceptance

In one fresh live attempt, disable the target in Parent, observe saved state, Switch User and enter the station. Read its disabled-child explanation, unavailable Request and absence of an authentication prompt. In another attempt, enable the target publicly and observe saved state before station entry; inspect offered lists, select the intended eligible child/approver and independently read the selection. Do not activate disabled controls. Empty-account fixture profiles are qualified by their own consumer.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_request_choices
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
Check **012** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
