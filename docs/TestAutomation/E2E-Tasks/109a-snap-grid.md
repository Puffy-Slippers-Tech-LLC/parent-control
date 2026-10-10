# 109a — Qualify Snap app-grid launches

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Snap app-grid route**. First scheduled consumer: [E2E-019, case 86](../E2E-Scenario-Recipes.md#e2e-019).
Read the [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **109** — APP01/02/03/04 and FLOW08 Snap command route.

## Implementation

Verify the prepared Snap baseline profile and reuse it and qualified command/result/activity readers. Bind SEARCH operations to the actual grid entries and compose the grid launch. Require a separately identified new window when one is already open; record the normal supported grid gesture explicitly.

`onpc_app_rows::native_search/native_launch_grid` currently bind the exact
Allowed native query; add explicit finite Snap entry bindings in those shared
SEARCH/launch operations. Qualification covers only this new GUI route and its
hidden/denied/restored results, with fresh owner/recipient checks. Reuse 109's
unchanged command denial and activity qualification; do not run its complete
Hard/Soft command history before every grid consumer. The separate-window
branch remains necessary for case 239's retained-work/new-launch distinction.

## Live VM acceptance

On the VM, launch a usable Snap fixture from the grid and observe a real input effect. Save a block publicly, require the declared hidden/denied grid result and use the qualified command route for an explicit denial witness when hidden. Restore access through Parent and verify the offered grid entry launches a distinguishable window while any retained activity remains.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_snap_grid
```
