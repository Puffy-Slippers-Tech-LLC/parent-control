# 051 — Compose the daily-only time profile

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW13 daily-only, fresh/same Parent entry with observed G=0**. First scheduled consumer: [E2E-008, case 21](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.
- **003d** — DESK04 direct logout command and independent GDM result.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the daily-only FLOW13 branch from fresh/same FLOW01, PARENT09, FLOW02 and DESK03. Require an already observed zero grant; refuse unexpected nonzero G. Optional revocation and retained Parent entry are qualified with the later grant-profile extension.

## Live VM acceptance

In a fresh installed VM attempt, reach Parent, read G=0, save a short positive allowance, verify D>0/G=0 and finish at GDM. Qualify an independently opened same-user Parent entry too. No real approval or retained-user return is required by this slice.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_time_profiles_daily
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
