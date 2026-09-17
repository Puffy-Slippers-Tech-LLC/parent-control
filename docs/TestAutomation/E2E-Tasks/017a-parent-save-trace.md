# 017a — Observe saving while a Parent control changes

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT08 transition mode**. First scheduled consumer: [E2E-035, case 159](../E2E-Scenario-Recipes.md#e2e-035).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **017** — PARENT08 snapshot saved/control states.
- **016a** — UI22.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind UI22 to Parent's saving and conflicting-control states. Arm observation and acknowledge readiness before one caller-owned Screen time limit change; collect the trace and terminal saved result without delaying the product.

## Live VM acceptance

On installed Parent, change Screen time limit once with the observer already active. Require the specified saving/control-inhibition samples and final saved state. A missed transient is unproven. Reuse the ordinary snapshot result; a final switch value cannot substitute for the trace.

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
