# 043 — Observe fresh child time denial and return

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add specific zero-time denial after correct authentication and DESK11 normal return to GDM. Reuse 043b for the fresh-child success route.

Reuse the delivered scope of tasks **043b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return**. First scheduled consumer: [E2E-015, case 49](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **041** — PARENT09, FLOW02.
- **043b** — GDM06/07 and FLOW15 fresh-child success.

## Implementation

Bind the intended child's fresh GDM recipient, success and explicit time-limit denial. Reuse two fresh recipient proofs and sealed single-use input. Then bind FLOW15(gdm, child, fresh, expected result) to that qualified GDM07 path. Implement DESK11's shared Escape route from the freshly observed rejected GDM prompt and independently observe the account list.

## Live VM acceptance

In separate live attempts, use Parent controls to prepare positive daily time or zero daily/no grant, then Switch User and perform a fresh child login through FLOW15. Require a usable child desktop for the former and the specific time-limit rejection after correct authentication for the latter. Return normally from rejection to GDM. Generic authentication failure is insufficient.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_unlock
```
