# 123a — Save a match draft after fixture removal

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 30–50 minutes.

Session exception: The retained editor, actual removal, catalogue absence, reinstall and restored-rule observations form one continuous qualification.

## Scope and prerequisites

Deliver **LIFE04 fixture remove/reinstall; PARENT15 retained-editor save; LIFE01 catalogue refresh**. First scheduled consumer: [E2E-020, case 111](../E2E-Scenario-Recipes.md#e2e-020).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries), [related block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **006** — LIFE04 install only.
- **044a** — DESK10 same-desktop window switching.
- **028** — LIFE01.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind verified fixture removal/reinstallation commands. Save the real open draft with PARENT15 while Parent still holds its pre-removal row. Then close/reopen Parent and reselect the child to observe the app's absence. Reinstall and refresh again before checking the retained rule; no removed-app row is expected in a freshly loaded catalogue.

## Live VM acceptance

On the live VM, leave a nondefault match draft open, remove the fixture through the shared administrator SSH package helper, return and Save. Close/reopen Parent through LIFE01, reselect the child and observe exclusion from the refreshed public catalogue. Reinstall through the shared administrator SSH package helper, reopen Parent again and independently read the retained rule before editing it.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_catalog_removal
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
