# 181h — Read the countdown explanation in UI tests

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
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
operate the identified countdown and independently read its explanation.
The existing localization test reads panel descriptions; a real hover result
is not yet registered. Retain lower-layer hover-state rules in
[indicator logic tests](../../../tests/child/indicator_logic.test.mjs).
Use the minimum supported input and public text readback, with no geometry or
popup/focus choreography assertions.

## UI acceptance

On the isolated Shell surface, require the explanation's public meaning and
current time value after supported hover on the identified control. Missing
text, wrong owner or stale target fails. Preserve shared input guards. This UI
result does not establish installed time accuracy, policy enforcement or expiry.

Run the maintained owners after implementing the missing UI assertion:

```sh
tools/run-tests ui --timeout 600 'tests/ui/test_child_shell_lifecycle.py'
tools/run-tests child-node 'tests/child/indicator_logic.test.mjs'
```
