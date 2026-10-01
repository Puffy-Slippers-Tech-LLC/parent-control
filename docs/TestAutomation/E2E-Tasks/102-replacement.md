# 102 — Compose expiry recovery through kiosk approval

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW11**. First scheduled consumer: [E2E-009, case 23](../E2E-Scenario-Recipes.md#e2e-009).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **062** — TIME04.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.

## Implementation

Compose DESK11, FLOW06, retained FLOW15 and APP02/04/03 with explicit retained-or-closed expectations. A legitimate unlock must precede activity inspection; the closed branch ends at APP02.

## Live VM acceptance

Let real child time expire, obtain a replacement through kiosk, unlock normally and observe the declared same usable activity or closed blocked app. Compare only earlier public observations; no claim about unseen events under lock.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_replacement
```
