# 077a — Read app rows and initial access choices

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT12; UI13 complete public app-row observations**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and the selected consumer's recipe.

Use the existing qualified source interfaces and guarded attempt envelope; no new capability prerequisite.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Register bounded app-row identity, access and match projections using UI01/02/03, then a complete UI13 row-set read. Use ordinary App Limits navigation and public scrolling when required. Return immutable semantic values; the caller supplies expected choices. Reuse installed baseline apps without adding native launch fixtures.

## Live VM acceptance

On a fresh installed VM, open Parent for the child, visit App Limits and read the declared app rows and their default Allowed choices. Require a complete bounded row set before asserting no blocks; an inaccessible or stale traversal cannot prove absence. Re-read from an independently opened App Limits page, and refuse a wrong child/page. No app-policy edits or launches are required.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_app_row_observations
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
