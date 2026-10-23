# F28 — Integrate Fedora recorded serial preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F27

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate `serial_harness.record_serial_journey` under
`execution.ScenarioContext` and its recorder. Read the full worker/recorder/
credential/getty/provisioning chain. Preserve setup/start ordering, private seals,
HAR09/HAR10 stage completion, durable observations before replies, boot continuity,
logout/session absence and owned worker shutdown. This is a distinct preparation
caller from standalone Smoke.
Qualify the same Smoke readiness step and recorder input binding on Fedora;
keep recorder-specific setup/start ordering and cleanup in this caller.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Preserve enforcing SELinux, exact native admissions and labels. Renew affected
Ubuntu checks after shared corrections.

## Acceptance and cleanup

Register/list the planned `check_fixture_recorded_serial` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_recorded_serial
```

Invoke the actual recorded harness preparation through shared readiness and
harmless native use. Stop before serial worker input or product assertions.
Host composition preserves serial/secret guards; recorder provenance binds the
same immutable fixture input. Finish recorder cleanup as well as VM/transport.
Complete shared qualification and the master's close-out.
