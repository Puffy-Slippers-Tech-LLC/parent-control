# 040a — Qualify daily-allowance boundaries

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **PARENT06 boundary/invalid values; PARENT08 validation**. First scheduled consumer: [E2E-035, case 158](../E2E-Scenario-Recipes.md#e2e-035).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **040** — PARENT05/06 valid ordinary values.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the complete daily preset/custom table in the scenario recipes. Implement accepted and invalid public projections, including the UI maximum 1439 and rejection of 1440; the broker's 1440 range remains engineering coverage. Reuse ordinary commits and save observations. Do not infer expectations from the current app.

## Live VM acceptance

On installed Parent, enable limits and qualify accepted custom 0, 1, 15 and 1439. For each invalid value in the recipe, start from saved 15, observe rejection and reopen the editor to read 15 unchanged. Case 158 owns enumeration of all 50 presets and the complete independent journey. Preserve/report any behavioral mismatch before changing expectations.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_allowance_boundaries
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
Check **040a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
