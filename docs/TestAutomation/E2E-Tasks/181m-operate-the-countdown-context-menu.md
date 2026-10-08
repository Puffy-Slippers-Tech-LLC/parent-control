# 181m — Operate the countdown context menu

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI28 and PANEL01/02**. First scheduled consumer: [E2E-008, case 22](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — Owned child countdown observations.

## Implementation

Use the shared `child-panel` Application UI API client. PANEL01 reads
`child-countdown-animation-toggle`; PANEL02 sets its canonical boolean through
UI17 and independently reads the final value. UI28 activates
`child-countdown-menu` only when ordinary menu entry is needed. Bind only the
public countdown-animation option; no secondary-click, focus or popup route
is a prerequisite of changing the preference.

## Live VM acceptance

On the VM, set the declared countdown-animation value and independently read the
final public option. Qualify independently supplied valid entry and wrong-owner
refusal through shared guards. The host UI owner covers local on/off behavior;
persistence and per-child isolation across session boundaries belong to cases
118 and 120. Case 22 verifies natural locking with animation enabled during its
existing wait. Menu closure or repeated toggling adds no acceptance result here.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_operate_the_countdown_context_menu
```
