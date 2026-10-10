# 182 — Prepare a daily balance that outlasts a soft exception

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW18**. First scheduled consumer: [E2E-038, case 164](../E2E-Scenario-Recipes.md#e2e-038).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.
- **079b** — FLOW19.
- **047** — APP04 and FLOW08 native usable-app observations.
- **052** — TIME01 public child-desktop remaining balance.
- **052c** — TIME03 bounded real wait.

## Implementation

Compose the exact daily-dominant-with-soft-exception recipe from qualified profiles, app use, retained Parent readback and TIME03. Do not edit allowance or app policy after approval; such edits restore launch blocks.

## Live VM acceptance

On the live VM, approve the prescribed small addition with soft apps, open S, switch away and wait while daily use pauses. Read G in the 60–90-second window and D at least 120 seconds, then return while G remains positive. Wrong inequalities fail preparation; no relabeling or top-up.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_prepare_a_daily_balance_that_outlasts_a_soft_exception
```
