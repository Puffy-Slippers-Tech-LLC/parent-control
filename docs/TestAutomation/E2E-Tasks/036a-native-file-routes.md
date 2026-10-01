# 036a — Observe policy results for Files launches

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add this route's Hard/Soft denial and expected prior-window closure. Reuse 036f's usable/new-window Files route; no substitute launch path.

Tasks **036f** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **APP01/02/03 native file-manager route**. First scheduled consumer: [E2E-019, case 74](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **036f** — APP01/02/03 native file-manager usable/new-window route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the file manager's offered launch action to the declared native fixture and independently observe its usable or blocked result. Register a supported separate-window launch for later retained-activity comparisons. Reuse the prepared standard fixture; special-path and AppImage copying stay with their own consumers.

## Live VM acceptance

On the live VM, launch the declared native fixture from the file manager and perform a normal action with a visible result. Open a distinguishable new window beside an earlier activity. Save Hard and Soft rules in Parent, then require this route's declared denied result and expected window closure. No alternative route substitutes for this action.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_native_file_routes
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
