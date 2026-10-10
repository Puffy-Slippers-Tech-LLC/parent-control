# 181h — Read the countdown explanation in UI tests

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver the **UI obligation for the countdown's readable explanation** under
the [UI coverage owner](../UI-and-E2E-Coverage.md). This row supplies no installed
E2E prerequisite or customer acceptance credit.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — Owned child countdown observations.

## Implementation

Extend the existing isolated-Shell owner
[test_child_shell_lifecycle.py](../../../tests/ui/test_child_shell_lifecycle.py)
and shared [Shell adapter](../../../tests/ui/child_shell_interaction.py) to
read `child-request-tooltip` through the shared `child-panel` Application UI
API client and independently compare its explanation with the public remaining
time. Retain lower-layer hover-state rules in
[indicator logic tests](../../../tests/child/indicator_logic.test.mjs).
Use the stable API ID and public text readback, with no geometry or
popup/focus choreography assertions.

`child_shell_interaction.main` currently inventories `child-request-tooltip`
but does not compare its public explanation. Add that missing assertion to the
existing shared interaction path; the Node tooltip-clock checks do not supply
the isolated-Shell public-text result.

## UI acceptance

On the isolated Shell surface, require the explanation's public meaning and
current time value from the identified API control. Missing
text, wrong owner or stale target fails. Preserve shared input guards. This UI
result does not establish installed time accuracy, policy enforcement or expiry.

Run the maintained owners after implementing the missing UI assertion:

```sh
tools/run-tests ui --timeout 600 'tests/ui/test_child_shell_lifecycle.py'
tools/run-tests child-node 'tests/child/indicator_logic.test.mjs'
```
