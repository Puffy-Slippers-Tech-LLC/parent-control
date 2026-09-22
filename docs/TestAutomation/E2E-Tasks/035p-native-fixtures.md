# 035p — Install the declared native app fixtures

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FIX04 native assets; LIFE04 fixture installation**. First scheduled consumer: [E2E-041, case 184](../E2E-Scenario-Recipes.md#e2e-041).
Read only the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope) and that consumer's selected recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — LIFE04 install only.
- **077a** — PARENT12; UI13 complete public app-row observations.

Use maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the finite A/H/S/N native fixture manifest to maintained public apps and verified package assets. Reuse FIX04 for powered-off transfer and LIFE04 for any required installation through the visible administrator terminal. Staging a package does not install it. Register only the fixed fixture install profile and the identities needed by the public catalogue; app launching and usability belong to a separate slice.

## Live VM acceptance

In a fresh guarded installed VM attempt, stage the declared assets, install missing fixtures through the real terminal/authentication route and read successful completion. Open Parent's App Limits and independently observe each declared launcher and its default access/match fields through PARENT12/UI13. Reopening the catalogue must show the same fixture set. Do not count a manifest entry as an installed launcher or seed app policy. Missing supported assets or public catalogue identities block this consumer.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_native_fixtures
```

The selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract).
Require independent valid entry, wrong-entry refusal and owned live VM cleanup.
Host checks and a diagnostic slice do not establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **035p** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
