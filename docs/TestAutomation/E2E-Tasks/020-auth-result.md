# 020 — Approve, reject or cancel a fresh request challenge

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits**. First scheduled consumer: [E2E-016, case 50](../E2E-Scenario-Recipes.md#e2e-016).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify queue rows; no predecessor brief is needed):

- **019** — REQUEST09, AUTH01 kiosk.
- **013** — REQUEST11/12 kiosk Cancel and Escape.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose two fresh AUTH01 checks, UI19 and submit for correct/wrong credentials; cancellation uses its declared public control. Observe explicit acceptance/rejection/dismissal and extend REQUEST11 accordingly. Later attempts require new challenges.

## Live VM acceptance

In separate live kiosk attempts, approve, enter a wrong password and cancel a fresh challenge. Read each form result and preserved choices. For successful approval, qualify both automatic exit and the offered immediate exit in separate attempts; each must return to GDM. Read the brief success before exit. A timeout is not rejection; credentials remain private.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_auth_result
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
Check **020** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
