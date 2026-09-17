# 035a — Qualify native fixtures with spaces and commas

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FIX04 special-path native assets; FILE05 and command-result bindings**. First scheduled consumer: [E2E-041, case 188](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify queue rows; no predecessor brief is needed):

- **036** — FILE07/04/05; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the two supported native path fixtures required by case 188: one space and one comma, their exact identical-copy destinations and distinct allowed N. Stage assets through FIX04; perform copies through FILE05. Reuse explicit command launch/result operations.

## Live VM acceptance

On the live VM, copy each declared executable through the file manager. Under publicly saved Hard and Soft rules, require original and identical-copy denial while N remains usable. Do not generalize this to arbitrary copied programs.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_qualify_native_fixtures_with_spaces_and_commas
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
If a complete E2E scenario passed, refresh coverage immediately after that case.
Use `tools/generate_test_coverage.sh`, which runs `tools/generate_test_coverage.py`.

Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and the selected family's status
in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md); leave unfinished scope pending.
Check **035a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
