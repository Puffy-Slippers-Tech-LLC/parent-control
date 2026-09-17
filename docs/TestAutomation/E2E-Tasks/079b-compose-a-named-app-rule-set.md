# 079b — Compose a named app-rule set

Estimate: 15–30 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW19**. First scheduled consumer: [E2E-006, case 13](../E2E-Scenario-Recipes.md#e2e-006).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose explicit FLOW01 entry, PARENT04(App Limits), one FLOW03 per named app/rule and DESK03. Supply the finite app list and current session/window ledger. Do not add allowance edits, approvals or app launches.

## Live VM acceptance

On the installed VM, configure a declared A/H/S set through Parent and finish at GDM. Return through qualified retained entry and read every saved row before editing. Repeat with an independently supplied Parent entry and a smaller explicit set.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_compose_a_named_app_rule_set
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
