# 181m — Operate the countdown context menu

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI28 and PANEL01/02**. First scheduled consumer: [E2E-037, case 162](../E2E-Scenario-Recipes.md#e2e-037).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **181h** — DESK12 showing countdown binding; UI27 and PANEL03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement one secondary click UI28 before PANEL01. Compose PANEL02 from UI17, Escape, menu absence and desktop observation. Bind only the public countdown-animation option.

## Live VM acceptance

On the VM, read default off, set on, close the menu, reopen and read on; set off and verify again. Return to a usable child desktop after each close. Persistence across session boundaries belongs to cases 162–163.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_operate_the_countdown_context_menu
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
