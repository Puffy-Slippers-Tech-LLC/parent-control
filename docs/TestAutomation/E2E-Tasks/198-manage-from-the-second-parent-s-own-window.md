# 198 — Manage from the second parent's own window

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW15/FLOW01 other-parent management entry**. First scheduled consumer: [E2E-051, case 251](../E2E-Scenario-Recipes.md#e2e-051).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **079** — PARENT16 and FLOW03 public app-policy editing.

## Implementation

Qualify the other administrator's own fresh/retained desktop and Parent window. Select the named child, navigate to Screen Limits before reading settings, and preserve separate window observations for the two parents.

Extend `journey_blocks.desktop_entry`, `onpc_desktop_session::enter_desktop`
and `onpc_parent::open_for_child/set_allowance` with the explicit second-parent
binding. Their current argument validation accepts only the primary parent
(and the child roles); approver support in the request form does not implement
Sam's management desktop. Bind owner/session/window receipts separately for
Jamie and Sam and refresh the selected child's public settings on each visit.
Reuse the qualified direct Parent launch and primary-parent entry; qualify
only the added management identity/return composition and focused wrong-owner
refusal, not the complete primary-parent provider matrix.

## Live VM acceptance

On the VM, open Parent normally under each administrator, manage a named child and switch between the two retained windows. Reselect and read current settings before edits; an approver identity from a system prompt is not proof of management entry.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_manage_from_the_second_parent_s_own_window
```
