# 079 — Compose one app match/access edit

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Compose FLOW03 match/access editing from the already-qualified leaves, including optional filters and independent row comparison.

Reuse the delivered scope of tasks **079c** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **PARENT16 and FLOW03 public app-policy editing**. First scheduled consumer: [E2E-005, case 7](../E2E-Scenario-Recipes.md#e2e-005).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **078** — PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts.
- **079c** — PARENT16 Allowed/Hard/Soft save and row readback.

## Implementation

Bind UI15 to one row's access choice, then compose PARENT16 from save and row readback. Compose FLOW03 only after PARENT10/11/13/15/16 and UI16 are qualified. Inputs declare the app, match draft, access choice and optional filters.

## Live VM acceptance

On installed Parent, save Allowed, Hard Blocked and Soft Blocked for the declared native row, reading every saved choice. Compose a full match/access edit and compare the row from an independent App Limits entry. This slice proves public editing; the separate app-result capability proves child enforcement.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_policy
```
