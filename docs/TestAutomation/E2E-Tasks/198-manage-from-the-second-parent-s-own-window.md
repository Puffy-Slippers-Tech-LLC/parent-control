# 198 — Manage from the second parent's own window

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW15/FLOW01 other-parent management entry**. First scheduled consumer: [E2E-051, case 251](../E2E-Scenario-Recipes.md#e2e-051).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **079** — PARENT16 and FLOW03 public app-policy editing.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify the other administrator's own fresh/retained desktop and Parent window. Select the named child, navigate to Screen Limits before reading settings, and preserve separate window observations for the two parents.

## Live VM acceptance

On the VM, open Parent normally under each administrator, manage a named child and switch between the two retained windows. Reselect and read current settings before edits; an approver identity from a system prompt is not proof of management entry.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_two_child_routine
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
