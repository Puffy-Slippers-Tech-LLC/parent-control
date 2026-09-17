# 017 — Observe Parent save results

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT08 snapshot saved/control states**. First scheduled consumer: [E2E-017, case 57](../E2E-Scenario-Recipes.md#e2e-017).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **010** — UI17.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement bounded snapshot observations of terminal saved state and control availability after a caller-owned change. Register only states reproducible through the selected public operation. Transition tracing is a separate scope and must not be inferred from a final snapshot.

## Live VM acceptance

On installed Parent, change Screen time limit through UI17, observe successful save and the resulting public control states, then read them again from an independently reached Parent window. A missing expected result or wrong child fails; no transient-saving claim is made.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_kiosk_choices
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
