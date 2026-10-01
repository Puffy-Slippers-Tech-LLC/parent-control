# 182 — Prepare a daily balance that outlasts a soft exception

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

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

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_prepare_a_daily_balance_that_outlasts_a_soft_exception
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
