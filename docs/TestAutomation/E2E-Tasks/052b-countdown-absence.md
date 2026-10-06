# 052b — Verify countdown availability in UI tests

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver the **UI obligation for countdown availability on desktop, locked and
greeter states** under the [UI coverage owner](../UI-and-E2E-Coverage.md).
This row supplies no installed E2E prerequisite or customer acceptance credit.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — Owned child countdown observations.

## Implementation

Extend the existing isolated-Shell owner
[test_child_shell_lifecycle.py](../../../tests/ui/test_child_shell_lifecycle.py)
and its shared `child-panel` Application UI API adapter with logical
countdown-availability and input-refusal checks. Keep
locked/greeter state branching in the existing
[indicator logic tests](../../../tests/child/indicator_logic.test.mjs).
Require complete public observations for UI absence; a disconnected observer,
incomplete API inventory or wrong owner cannot prove it. Do not manufacture real GDM
sessions inside a host preview. Any unavailable public preview state remains a
specific unimplemented UI obligation.

## UI acceptance

Verify availability in supported isolated desktop/locked/greeter states and
restoration after the relevant state change. Preserve account ownership and
wrong-surface refusal in shared observers. Installed cross-account policy
isolation, legitimate retained entry and actual natural locking remain the
customer journeys' independent functional results.

Run the maintained owners after implementing the missing UI assertions:

```sh
tools/run-tests ui --timeout 600 'tests/ui/test_child_shell_lifecycle.py'
tools/run-tests child-node 'tests/child/indicator_logic.test.mjs'
```
