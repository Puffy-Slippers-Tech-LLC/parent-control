# F25 — Integrate Ubuntu serial qualification

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F23

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate standalone serial `Smoke`/`check_graphical_serial` and authenticated
install/refusal aliases. Read the complete credential/getty/bootstrap/asset chain.
Retain preboot credential/getty lifetime, secret recipients, recording seals and
single-use input; move reusable fixture bytes to shared owned SSH before serial
input. Host composition preserves successful-install reboot versus refused-install
logout/no-reboot assertions. Recorded serial remains gated until its own tasks.
Reuse F22's post-SSH Smoke readiness step for these aliases; retain their
credential/getty and recipient guards at the existing boundaries.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Keep platform-specific corrections in their shared owning adapter.

## Acceptance and cleanup

Register/list the planned `check_fixture_serial` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_serial
```

Exercise actual standalone serial preparation and harmless native use, then
stop before serial input/authentication or product assertions. Host tests bind
authenticated-install/refusal aliases without claiming package/login acceptance.
Complete shared qualification and the master's close-out.
