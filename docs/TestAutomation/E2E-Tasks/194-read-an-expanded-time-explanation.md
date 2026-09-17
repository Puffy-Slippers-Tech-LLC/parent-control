# 194 — Read an expanded time explanation

Estimate: 20–40 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT20**. First scheduled consumer: [E2E-036, case 161](../E2E-Scenario-Recipes.md#e2e-036).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **040** — PARENT05/06 valid ordinary values.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Register daily, one-time and total text projections, display precision and monotonic observation time. Read only an already expanded showing explanation; expansion/navigation belongs to PARENT09.

## Live VM acceptance

On installed Parent, enable limits and save an ordinary allowance. Explicit UI inputs expand the explanation before PARENT20 is called; independently read all three balances twice without changing expanded state. A collapsed explanation or wrong child refuses without opening it.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_allowance
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
