# 182 — Prepare a daily balance that outlasts a soft exception

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FLOW18**. First scheduled consumer: [E2E-038, case 164](../E2E-Scenario-Recipes.md#e2e-038).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.
- **079b** — FLOW19.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **052a** — TIME02 minute/final-second ticks.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the exact daily-dominant-with-soft-exception recipe from qualified profiles, app use, retained Parent readback and TIME03. Do not edit allowance or app policy after approval; such edits restore launch blocks.

## Live VM acceptance

On the live VM, approve the prescribed small addition with soft apps, open S, switch away and wait while daily use pauses. Read G in the 60–90-second window and D at least 120 seconds, then return while G remains positive. Wrong inequalities fail preparation; no relabeling or top-up.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_prepare_a_daily_balance_that_outlasts_a_soft_exception
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
Check **182** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
