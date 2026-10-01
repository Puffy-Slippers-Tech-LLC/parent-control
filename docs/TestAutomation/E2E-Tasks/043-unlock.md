# 043 — Observe fresh child time denial and return

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add specific zero-time denial after correct authentication and DESK11 normal return to GDM. Reuse 043b for the fresh-child success route.

Tasks **043b** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return**. First scheduled consumer: [E2E-015, case 49](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#sign-in-and-desktop-entry), [related block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **041** — PARENT09, FLOW02.
- **043b** — GDM06/07 and FLOW15 fresh-child success.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the intended child's fresh GDM recipient, success and explicit time-limit denial. Reuse two fresh recipient proofs and sealed single-use input. Then bind FLOW15(gdm, child, fresh, expected result) to that qualified GDM07 path. Implement DESK11's shared Escape route from the freshly observed rejected GDM prompt and independently observe the account list.

## Live VM acceptance

In separate live attempts, use Parent controls to prepare positive daily time or zero daily/no grant, then Switch User and perform a fresh child login through FLOW15. Require a usable child desktop for the former and the specific time-limit rejection after correct authentication for the latter. Return normally from rejection to GDM. Generic authentication failure is insufficient.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_unlock
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
