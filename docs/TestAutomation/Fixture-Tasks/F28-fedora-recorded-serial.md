# F28 — Integrate Fedora recorded serial preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F27

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate `serial_harness.record_serial_journey` under
`execution.ScenarioContext` and its recorder. Read the full worker/recorder/
credential/getty/provisioning chain. Preserve setup/start ordering, private seals,
HAR09/HAR10 stage completion, durable observations before replies, boot continuity,
logout/session absence and owned worker shutdown. This is a distinct preparation
caller from standalone Smoke.

Reuse the execution-owned immutable input and single SSH provisioner on clean
captures. Bind readiness to the actual restored/rebound boot and attempt.
Enable only this qualified target/branch; other unmigrated branches must refuse.
Preserve enforcing SELinux, exact native admissions and labels. Renew affected
Ubuntu checks after shared corrections.

## Acceptance and cleanup

Run exact affected host composition/provenance/ownership safety selections.
Register/list the planned `check_fixture_recorded_serial` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_recorded_serial
```

Invoke the actual recorded harness preparation through shared readiness and
harmless native use. Stop before serial worker input or product assertions.
Host composition preserves serial/secret guards; recorder provenance binds the
same immutable fixture input. Finish recorder cleanup as well as VM/transport.
Prove selected manifest bytes independently, positive runtime use, fresh readiness,
missing/incompatible refusal before input and no version switch under host edits.
No complete fixture collection is copied into results; preserve scenario mutations.
Finish watched owned restoration and credential/staging/input/transport cleanup.
Update delivered runner/support owners and close through the
[master](../Fixture-Execution-Plan.md). This supplies no customer/E2E acceptance.
