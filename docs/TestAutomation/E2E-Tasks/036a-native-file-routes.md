# 036a — Observe policy results for Files launches

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add this route's Hard/Soft denial and expected prior-window closure. Reuse 036f's usable/new-window Files route; no substitute launch path.

Reuse the delivered scope of tasks **036f** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 native file-manager route**. First scheduled consumer: [E2E-019, case 74](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **036f** — APP01/02/03 native file-manager usable/new-window route.

## Implementation

Bind the file manager's offered launch action to the declared native fixture and independently observe its usable or blocked result. Register a supported separate-window launch for later retained-activity comparisons. Reuse the prepared standard fixture; special-path and AppImage copying stay with their own consumers.

## Live VM acceptance

On the live VM, capture the required activity through 036f's qualified Files
launch, save Hard and Soft rules in Parent, and require the declared denied
launch and prior-window closure for each distinct policy result. Reuse unchanged
usable/new-window qualification from 036f; rerun it only when affected. No
alternative launch route substitutes for the tested Files action.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_native_file_routes
```
