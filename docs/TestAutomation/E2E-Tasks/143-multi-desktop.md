# 143 — Qualify distinct retained desktops for one child

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FLOW14 same-child multi-desktop scope**. First scheduled consumer: [E2E-007, case 18](../E2E-Scenario-Recipes.md#e2e-007).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** A supported public route must create and revisit distinct same-child desktops. Resuming one desktop twice cannot qualify it.

Required implemented capabilities (IDs identify queue rows; no predecessor brief is needed):

- **047a** — FLOW09 and FLOW14 distinct-user retention.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **050** — PARENT17, PARENT18.
- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Demonstrate a supported customer route to distinct same-child desktops and extend FLOW14 only if it exists. Repeated GDM selection may resume one desktop. Otherwise keep the precise obligation blocked for explicit system/customer ownership reconciliation.

## Live VM acceptance

Live UI actions must create two separately identifiable public activities for the same child, revisit both, and preserve an unrelated user's activity. No backend session creation/probes. A failed applicability check is not a completed scenario.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_multi_desktop
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
Check **143** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
