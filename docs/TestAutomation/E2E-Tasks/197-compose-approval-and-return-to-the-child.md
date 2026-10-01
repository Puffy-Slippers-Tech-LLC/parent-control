# 197 — Compose overlay approval and return

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW20 overlay new/open form**. First scheduled consumer: [E2E-048, case 223](../E2E-Scenario-Recipes.md#e2e-048).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052** — TIME01 child-desktop presence and limits-off absence.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the overlay branches of FLOW04 and FLOW05, then TIME01/UI12 on the same child desktop. Accept explicit new/open form entry and earlier public balance observations. No hidden allowance, policy preparation or desktop transition. Keep the kiosk branch pending.

## Live VM acceptance

In separate live attempts, supply a usable child desktop for new-form entry and an independently prepared overlay for open-form entry. Approve once, observe automatic form disappearance and the same usable child desktop, then compare countdown with the earlier public balance plus the requested interval and measured elapsed time. Missing, wrong-child or kiosk entry refuses without preparatory input.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_compose_approval_and_return_to_the_child
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
