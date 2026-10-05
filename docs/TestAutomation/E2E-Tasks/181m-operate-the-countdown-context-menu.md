# 181m — Operate the countdown context menu

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI28 and PANEL01/02**. First scheduled consumer: [E2E-037, case 162](../E2E-Scenario-Recipes.md#e2e-037).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — Owned child countdown observations.

## Implementation

Implement one secondary click UI28 before PANEL01. Compose PANEL02 from UI17 and independent final option readback; any menu dismissal needed for later input is shared navigation. Bind only the public countdown-animation option.

## Live VM acceptance

On the VM, set the declared countdown-animation value and independently read the
final public option. Qualify independently supplied valid entry and wrong-owner
refusal through shared guards. The host UI owner covers local on/off behavior;
persistence and per-child isolation across session boundaries belong to cases
162–163. Menu closure or repeated toggling adds no acceptance result here.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_operate_the_countdown_context_menu
```
