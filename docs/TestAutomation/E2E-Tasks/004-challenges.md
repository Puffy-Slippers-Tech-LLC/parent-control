# 004 — Allow distinct single-use authentication challenges

Estimate: 40–60 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: The shared single-use challenge ledger requires multiple real authentications and the complete affected credential/retained regression set.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **UI19/GDM05 distinct single-use authentication challenges**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 current Shell logout/confirmation route and independently observed GDM return.
- **004a** — JourneyPlan repeated invocation IDs and assertion placement.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Replace the one-authentication-per-worker limitation with explicit, single-use challenge context for UI19/GDM05. Use the qualified repeated-stage interface. Preserve wrong-recipient refusal, two fresh intended-recipient checks, sealed capture, fixed secret input and a terminal failure latch; never clear the latch to authenticate again.

## Live VM acceptance

In one guarded VM attempt, authenticate the Parent, log out through the normal UI, then authenticate again with a new challenge. Reject stale/reused proofs in safety regressions; no reset of the existing failure latch. After external-provider route qualification, run affected credential safety and retained cases 1, 3, 4, 5, 151.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_challenges
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
Check **004** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
