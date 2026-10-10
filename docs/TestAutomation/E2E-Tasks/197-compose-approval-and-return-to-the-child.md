# 197 — Compose overlay approval and return

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW20 overlay new/open form**. First scheduled consumer: [E2E-048, case 223](../E2E-Scenario-Recipes.md#e2e-048).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **052** — TIME01 child-desktop presence and limits-off absence.

## Implementation

Compose the overlay branches of FLOW04 and FLOW05, then TIME01/UI12 on the same child desktop. Accept explicit new/open form entry and earlier public balance observations. No hidden allowance, policy preparation or desktop transition. Keep the kiosk branch pending.

## Live VM acceptance

In separate live attempts, supply a usable child desktop for new-form entry and an independently prepared overlay for open-form entry. Approve once, observe automatic form disappearance and the same usable child desktop, then compare countdown with the earlier public balance plus the requested interval and measured elapsed time. Missing, wrong-child or kiosk entry refuses without preparatory input.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_compose_approval_and_return_to_the_child
```
