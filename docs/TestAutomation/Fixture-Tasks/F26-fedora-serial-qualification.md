# F26 — Integrate Fedora serial qualification

Acceptance: installed
Targets: onpc-Fedora44
Requires: F25

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Qualify F25's standalone serial `Smoke`/`check_graphical_serial` and authenticated
install/refusal preparation aliases. Reuse its helper, selector and history;
change only target gates and evidenced Fedora differences. Read complete affected
functions and necessary credential/getty/bootstrap/asset callers.
Retain preboot credential/getty lifetime, secret recipients, recording seals and
single-use input; move reusable fixture bytes to shared owned SSH before serial
input. Host composition preserves successful-install reboot versus refused-install
logout/no-reboot assertions. Recorded serial remains gated until its own tasks.
Qualify the shared post-SSH Smoke readiness step for Fedora's serial aliases;
retain their credential/getty and recipient guards at the existing boundaries.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Preserve enforcing SELinux, exact native admissions and labels. Renew Ubuntu proof
only where invalidated under the design's [validation rule](../Fixture-Design.md#validation-reuse-and-invalidation).

## Acceptance and cleanup

Confirm F25's existing `check_fixture_serial` binding lists Fedora before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_serial
```

Exercise actual standalone serial preparation once and harmless native use, then
stop before serial input/authentication or product assertions. Host tests bind
authenticated-install/refusal aliases without claiming package/login acceptance.
Reuse F25/shared safety proof. Do not execute successful/refused installs,
login/logout or reboot journeys, or add an alias-by-alias live matrix.
Complete shared qualification and the master's close-out.
