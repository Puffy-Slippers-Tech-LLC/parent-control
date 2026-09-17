# 019 — Qualify the real selected-parent approval prompt

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **REQUEST09, AUTH01 kiosk**. First scheduled consumer: [E2E-016, case 50](../E2E-Scenario-Recipes.md#e2e-016).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify queue rows; no predecessor brief is needed):

- **012a** — REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk.
- **004** — UI19/GDM05 distinct single-use authentication challenges.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify AUTH01 over the actual system agent first: selected parent, child, duration, app choice and sole empty masked focused field. Its qualification reaches the prompt through an explicit UI01/UI02/UI04 Request input. Only then compose valid REQUEST09 from those leaves and AUTH01. Add owned kiosk-agent routing without treating agent metadata as an approval result.

## Live VM acceptance

On the VM, prepare a valid kiosk request, submit once and inspect the real challenge. Refuse wrong parent/request and nonempty/stale field proofs; an otherwise ready form rejects an invalid custom duration with validation and no prompt when Request is selected, while unavailable forms keep Request disabled. Finish through the normal agent Cancel control.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_auth_prompt
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
Check **019** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
