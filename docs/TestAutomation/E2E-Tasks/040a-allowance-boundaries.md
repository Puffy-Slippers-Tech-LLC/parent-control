# 040a — Qualify daily-allowance boundaries

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT06 boundary/invalid values; PARENT08 validation**. First scheduled consumer: [E2E-035, case 158](../E2E-Scenario-Recipes.md#e2e-035).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **040** — PARENT05/06 valid ordinary values.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the complete daily preset/custom table in the scenario recipes. Implement accepted and invalid public projections, including the UI maximum 1439 and rejection of 1440; the broker's 1440 range remains engineering coverage. Reuse ordinary commits and save observations. Do not infer expectations from the current app.

## Live VM acceptance

On installed Parent, enable limits and qualify accepted custom 0, 1, 15 and 1439. For each invalid value in the recipe, start from saved 15, observe rejection and reopen the editor to read 15 unchanged. Case 158 owns enumeration of all 50 presets and the complete independent journey. Preserve/report any behavioral mismatch before changing expectations.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_allowance_boundaries
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
