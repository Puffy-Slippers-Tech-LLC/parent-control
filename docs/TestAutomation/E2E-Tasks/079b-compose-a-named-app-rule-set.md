# 079b — Compose a named app-rule set

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 15–30 minutes.

## Scope and prerequisites

Deliver **FLOW19**. First scheduled consumer: [E2E-006, case 13](../E2E-Scenario-Recipes.md#e2e-006).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose explicit FLOW01 entry, PARENT04(App Limits), one FLOW03 per named app/rule and DESK03. Supply the finite app list and current session/window ledger. Do not add allowance edits, approvals or app launches.

## Live VM acceptance

On the installed VM, configure a declared A/H/S set through Parent and finish at GDM. Return through qualified retained entry and read every saved row before editing. Repeat with an independently supplied Parent entry and a smaller explicit set.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_compose_a_named_app_rule_set
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
