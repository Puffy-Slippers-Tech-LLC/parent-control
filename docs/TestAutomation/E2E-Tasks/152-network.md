# 152 — Change connectivity through public network controls

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FEED09 Parent retry/recovery over qualified LIFE06**. First scheduled consumer: [E2E-033, case 157](../E2E-Scenario-Recipes.md#e2e-033).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

**Gate:** Authorized sending and a public connectivity route that preserves the guarded observation channel.

Required implemented capabilities (IDs identify queue rows; no predecessor brief is needed):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **193** — LIFE06.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse LIFE06's already-qualified public disconnect/reconnect controls. Extend FEED09 only for real retry and recovery during one authorized submission, preserving the normal retry window and safe observation transport. No transport fault injection or forged response.

## Live VM acceptance

In the authorized live retry attempt, disconnect through UI, submit once, observe retry, reconnect before its deadline and observe automatic success for that same submission. If network controls also sever required harness access with no supported route, retain the blocker.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_network
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
Check **152** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
