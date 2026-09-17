# 079 — Save app access choices and compose one rule edit

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT16 and FLOW03 public app-policy editing**. First scheduled consumer: [E2E-005, case 7](../E2E-Scenario-Recipes.md#e2e-005).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **078** — PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind UI15 to one row's access choice, then compose PARENT16 from save and row readback. Compose FLOW03 only after PARENT10/11/13/15/16 and UI16 are qualified. Inputs declare the app, match draft, access choice and optional filters.

## Live VM acceptance

On installed Parent, save Allowed, Hard Blocked and Soft Blocked for the declared native row, reading every saved choice. Compose a full match/access edit and compare the row from an independent App Limits entry. This slice proves public editing; the separate app-result capability proves child enforcement.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_policy
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
