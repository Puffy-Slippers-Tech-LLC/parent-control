# 014 — Compose prepared request choices

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FLOW04 kiosk**. First scheduled consumer: [E2E-015, case 47](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **012a** — REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk.
- **013** — REQUEST11/12 kiosk Cancel and Escape.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose kiosk REQUEST01 → REQUEST03/04/05/06/08 in the documented order with explicit child, approver, duration and app choice. Receive an independently prepared enabled target; the composite does not change Parent policy.

## Live VM acceptance

On the live VM, enable the target through Parent with UI17/PARENT08 and use DESK03 to reach GDM. In the station, prepare a request, read back all chosen values and estimate, then exit normally. Also supply an independently opened form to qualify entry=open without reopening it. Re-enter from an independent GDM state for entry=new and reproduce the result with fresh stage IDs.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_request_flow
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
Check **014** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
