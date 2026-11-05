# 109a — Qualify allowed Snap app-grid launches

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Allowed Snap app-grid route**. First scheduled consumer: [E2E-019, case 86](../E2E-Scenario-Recipes.md#e2e-019).
Read the [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **109b** — APP01/02/03/04 and FLOW08 Snap command usable/new-window route.

## Implementation

Verify the prepared Snap baseline profile and reuse it and qualified command/result/activity readers. Bind SEARCH operations to the actual grid entries and compose the grid launch. Require a separately identified new window when one is already open; record the normal supported grid gesture explicitly.

`onpc_app_rows::native_search/native_launch_grid` currently bind the exact
Allowed native query; add explicit finite Snap entry bindings in those shared
SEARCH/launch operations. Qualify only Allowed launch, input effect and activity,
with fresh owner/recipient checks. Reuse 109b's command/activity mechanics.
Task 109's denial/closure history is deferred, not a prerequisite. Apply the
[shared Snap boundary](../E2E-Execution-Instructions.md#snap-acceptance-boundary).
Retain the distinguishable second-window check as an Allowed operation; it
supplies no policy-enforcement or deferred case-239 credit.

## Live VM acceptance

On the VM, independently read the declared Allowed Snap row, launch its usable
fixture from the grid and observe a real input effect. Launch a distinguishable
second window using the supported grid gesture and verify the original activity
is preserved. Retain valid independent entry and wrong-fixture/owner refusal.
Do not save a block, test hidden/denied/restored results or invoke task 109's
qualification. Missing Allowed-route observations remain ordinary task failures;
the known enforcement limitation is not a choice or investigation gate.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_snap_grid
```
