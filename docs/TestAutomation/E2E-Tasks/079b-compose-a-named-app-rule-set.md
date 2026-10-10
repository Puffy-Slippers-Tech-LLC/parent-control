# 079b — Compose a named app-rule set

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 15–30 minutes.

## Scope and prerequisites

Deliver **FLOW19**. First scheduled consumer: [E2E-006, case 13](../E2E-Scenario-Recipes.md#e2e-006).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **044b** — Explicit retained Parent desktop/window entry; no child-desktop matrix.

## Implementation

Compose explicit FLOW01 entry, PARENT04(App Limits), one FLOW03 per named app/rule and DESK03. Supply the finite app list and current session/window ledger. Do not add allowance edits, approvals or app launches.

Reuse `policy_edits.policy_edit` / `onpc_app_rows::edit_policy` and
`onpc_parent::open_for_child`. Their current policy binding is Jordan's native
fixture A, not an arbitrary A/H/S set: extend the finite named-app arguments and
independent saved-row comparisons needed by case 13 before qualifying FLOW19.
Retain fresh/same/retained Parent entry as explicit caller arguments; consume
044b's unchanged retained-window operation without replaying its child/session
qualification history.

## Live VM acceptance

On the installed VM, configure a declared A/H/S set through Parent and finish at GDM. Return through qualified retained entry and read every saved row before editing. Repeat with an independently supplied Parent entry and a smaller explicit set.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_compose_a_named_app_rule_set
```
