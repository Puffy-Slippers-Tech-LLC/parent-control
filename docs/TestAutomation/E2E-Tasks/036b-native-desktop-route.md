# 036b — Observe policy results for desktop launches

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add desktop-specific blocked results after a public Parent save. Reuse 036g/036h's usable and separate-window bindings; missing DING support remains a blocker.

Reuse the delivered scope of tasks **036g**, **036h** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 native desktop route**. First scheduled consumer: [E2E-019, case 70](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036h** — APP01/02 desktop separate-window route.

Its transitive prerequisites retain bounded shared file preparation, verified
native baseline assets/launchers and native policy-result observations.

## Implementation

Reuse 036g's verified entry and shared command/API placement and trust
preparation. Bind its public desktop activation and independently observe usable
or blocked results. Missing desktop support blocks this route; do not install
another desktop extension or substitute a different launcher.

The installed desktop icon is owned by DING. Reuse 036g/036h's qualified
icon/activation and separate-window bindings with wrong-icon and ambiguous-owner
refusal. This task adds only the policy-result observations; it does not repeat
launcher preparation or add selection/menu permutations. Search, command or
file-manager activation cannot replace the tested desktop route.

## Live VM acceptance

On the live VM, capture the required activity through the qualified desktop
entry, apply each declared public Parent block and observe this route's denied
launch and expected prior-window closure. Reuse unchanged usable/separate-window
evidence from 036g/036h; rerun an affected binding when necessary. Qualify
independently supplied desktop entry and wrong-target refusal. Another launcher
cannot establish the desktop policy result.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_native_desktop_route
```
