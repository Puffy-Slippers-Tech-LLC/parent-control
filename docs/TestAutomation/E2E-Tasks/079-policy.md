# 079 — Compose one app match/access edit

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Compose FLOW03 match/access editing from the already-qualified leaves, including optional filters and independent row comparison.

Tasks **079c** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **PARENT16 and FLOW03 public app-policy editing**. First scheduled consumer: [E2E-005, case 7](../E2E-Scenario-Recipes.md#e2e-005).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **078** — PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts.
- **079c** — PARENT16 Allowed/Hard/Soft save and row readback.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind UI15 to one row's access choice, then compose PARENT16 from save and row readback. Compose FLOW03 only after PARENT10/11/13/15/16 and UI16 are qualified. Inputs declare the app, match draft, access choice and optional filters.

## Live VM acceptance

On installed Parent, save Allowed, Hard Blocked and Soft Blocked for the declared native row, reading every saved choice. Compose a full match/access edit and compare the row from an independent App Limits entry. This slice proves public editing; the separate app-result capability proves child enforcement.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_policy
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
