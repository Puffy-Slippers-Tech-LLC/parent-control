# 044 — Visit both retained child desktops

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add both retained child bindings and complete explicit FLOW15 modes. Reuse 044b's Parent entry; keep other-parent management under task 198.

Reuse the delivered scope of tasks **044b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **DESK09; FLOW15 and FLOW01 retained scopes**. First scheduled consumer: [E2E-018, case 58](../E2E-Scenario-Recipes.md#e2e-018).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **044b** — DESK09 and FLOW01 retained Parent entry.

Its transitive prerequisites retain GDM02 retained-child lock entry, DESK08/11
unlock/denial and DESK10 same-desktop window switching.

## Implementation

Implement retained-user routing, reusing normal DESK10 window switching and the qualified fresh-child FLOW15 branch. Extend FLOW15 for explicit same/retained/lock/denied entry. Reuse [qualified retained Parent entry](../E2E-Building-Blocks.md#retained-parent-desktop-and-window-entry), `retained_parent_entry` and `onpc_parent::open_for_child`'s explicit retained/same-user branches; extend their finite account/child bindings as needed without reselection hiding state. Qualify the Parent and both child account/recipient bindings required for these entries. A retained Parent window may be on App Limits: reach Screen Limits with PARENT04 before reading PARENT03. The second administrator's management desktop/window remains the separate other-parent scope.

## Live VM acceptance

On the VM, leave recognizable windows on child and Parent desktops, switch between them, unlock normally and foreground the same windows. Wrong entry modes fail without repairing state; compare retained public activity before relaunching anything.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_retained_entry
```
