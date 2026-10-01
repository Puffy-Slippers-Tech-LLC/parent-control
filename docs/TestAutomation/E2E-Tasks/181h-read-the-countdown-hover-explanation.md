# 181h — Read the countdown hover explanation

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **DESK12 showing countdown binding; UI27 and PANEL03**. First scheduled consumer: [E2E-011, case 27](../E2E-Scenario-Recipes.md#e2e-011).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — TIME01 child-desktop presence and limits-off absence.

## Implementation

Bind the already-showing countdown target under DESK12, implement one normal hover input UI27, then compose PANEL03 from the fresh target and tooltip text. Qualify desktop countdown only.

## Live VM acceptance

With publicly prepared usable child time on the VM, read countdown, hover the real control and read its explanation. Independently supplied child entry must work. Missing hover text, wrong account or stale target fails; no fullscreen route is claimed.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_read_the_countdown_hover_explanation
```
