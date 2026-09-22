# 051 — Compose the daily-only time profile

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FLOW13 daily-only, fresh/same Parent entry with observed G=0**. First scheduled consumer: [E2E-008, case 21](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.
- **003d** — DESK04 current Shell logout/confirmation route and independently observed GDM return.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the daily-only FLOW13 branch from fresh/same FLOW01, PARENT09, FLOW02 and DESK03. Require an already observed zero grant; refuse unexpected nonzero G. Optional revocation and retained Parent entry are qualified with the later grant-profile extension.

## Live VM acceptance

In a fresh installed VM attempt, reach Parent, read G=0, save a short positive allowance, verify D>0/G=0 and finish at GDM. Qualify an independently opened same-user Parent entry too. No real approval or retained-user return is required by this slice.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_time_profiles_daily
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
Check **051** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
