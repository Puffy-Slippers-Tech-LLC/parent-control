# 052 — Observe the child countdown or its absence

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **TIME01 child-desktop presence and limits-off absence**. First scheduled consumer: [E2E-015, case 49](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Register bounded child-desktop countdown text and complete absence observations on the positively identified child desktop. Return an immutable observation for the caller's expected balance or limits-off state. Qualify this surface independently of lock/GDM absence and tick measurement.

## Live VM acceptance

In separate live attempts, prepare positive daily time or disabled limits through Parent, then enter the child fresh. Require the countdown within declared elapsed-time/rounding bounds for enabled limits, and stable absence on the recognized usable desktop for disabled limits. Independently reached child entry must work; wrong accounts, stale or incomplete reads refuse.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_countdown
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
