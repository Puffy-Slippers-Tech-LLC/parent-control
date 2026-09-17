# 180 — Set an allowance for a named child

Estimate: 15–30 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup**. First scheduled consumer: [E2E-036, case 161](../E2E-Scenario-Recipes.md#e2e-036).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **041** — PARENT09, FLOW02.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify FLOW01's same-user Parent entry first, then compose FLOW16 from explicit parent/child/source/window entry and FLOW02's initial allowance/final limit state. Keep navigation and final Parent surface explicit; retained and second-parent bindings use their separately qualified entry scopes.

## Live VM acceptance

On installed Parent, use fresh/new and independently open same-user entries to set the selected child's allowance to zero and then an ordinary positive value. Read saved settings and balances without logging out implicitly. Wrong selected-child/window input must refuse.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_set_an_allowance_for_a_named_child
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
