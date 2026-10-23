# F27 — Integrate Ubuntu recorded serial preparation

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F26

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate `serial_harness.record_serial_journey` under
`execution.ScenarioContext` and its recorder. Read complete affected functions
and necessary worker/recorder/credential/getty/provisioning callers.
Preserve setup/start ordering, private seals,
HAR09/HAR10 stage completion, durable observations before replies, boot continuity,
logout/session absence and owned worker shutdown. This is a distinct preparation
caller from standalone Smoke.
Reuse the qualified post-SSH Smoke readiness step. Bind its selected input and
readiness to recorder provenance before the ready reply; keep recorder-specific
setup/start ordering and cleanup in this caller.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Keep platform-specific corrections in their shared owning adapter.

## Acceptance and cleanup

Register/list the planned `check_fixture_recorded_serial` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_recorded_serial
```

Invoke the actual recorded harness preparation once through shared readiness and
harmless native use. Stop before serial worker input or product assertions.
Host composition preserves serial/secret guards; recorder provenance binds the
same immutable fixture input. Finish recorder cleanup as well as VM/transport.
Reuse F25's Smoke readiness and shared recording/ownership safety proof under
the design's [validation rule](../Fixture-Design.md#validation-reuse-and-invalidation).
Verify the new recorder binding directly; do not requalify the complete recorder
or run HAR09/HAR10, login/logout or product scenarios for fixture acceptance.
Complete shared qualification and the master's close-out.
