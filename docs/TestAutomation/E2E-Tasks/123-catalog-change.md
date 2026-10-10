# 123 — Keep an unsaved match draft across a fixture update

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **LIFE04 fixture update; PARENT15 retained-editor save; LIFE01 catalogue refresh**. First scheduled consumer: [E2E-020, case 110](../E2E-Scenario-Recipes.md#e2e-020).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries), [related block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **006** — LIFE04 install only.
- **028** — LIFE01.

## Implementation

Bind a verified old/new fixture package pair and extend LIFE04(update). Leave the real Edit Match Rule draft open while the package changes, then Save through the same owned editor's Application UI API operation. Package commands run over SSH, so no supporting window or desktop focus change is needed.

## Live VM acceptance

On the VM, set a nondefault unsaved match draft, update the fixture through the shared administrator SSH package helper and Save from that still-open editor. Close/reopen Parent through LIFE01, reselect the child and independently read the refreshed public app row and expected rule; save-time target resolution does not refresh existing rows. Preserve owned cleanup; no autosave pause or saved-preference probe.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_catalog_change
```
