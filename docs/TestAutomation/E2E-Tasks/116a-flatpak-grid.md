# 116a — Qualify Flatpak app-grid launches

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Flatpak app-grid route**. First scheduled consumer: [E2E-019, case 98](../E2E-Scenario-Recipes.md#e2e-019).
Read the [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **116** — APP01/02/03/04 and FLOW08 Flatpak command route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the staged Flatpak fixtures and qualified command/result/activity readers. Bind SEARCH operations to the actual grid entries and compose the grid launch. Require a separately identified new window when one is already open; record the normal supported grid gesture explicitly.

## Live VM acceptance

On the VM, launch a usable Flatpak fixture from the grid and observe a real input effect. Save a block publicly, require the declared hidden/denied grid result and use the qualified command route for an explicit denial witness when hidden. Restore access through Parent and verify the offered grid entry launches a distinguishable window while any retained activity remains.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_flatpak_grid
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
