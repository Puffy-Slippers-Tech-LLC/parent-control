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

Reuse the execution-owned immutable input and single SSH provisioner on clean
captures. Bind readiness to the actual restored/rebound boot and attempt.
Enable only this qualified target/branch; other unmigrated branches must refuse.
Keep platform-specific corrections in their shared owning adapter.

## Acceptance and cleanup

Run exact affected host composition/provenance/ownership safety selections.
Register/list the planned `check_fixture_serial` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_serial
```

Exercise actual standalone serial preparation and harmless native use, then
stop before serial input/authentication or product assertions. Host tests bind
authenticated-install/refusal aliases without claiming package/login acceptance.
Prove selected manifest bytes independently, positive runtime use, fresh readiness,
missing/incompatible refusal before input and no version switch under host edits.
No complete fixture collection is copied into results; preserve scenario mutations.
Finish watched owned restoration and credential/staging/input/transport cleanup.
Update delivered runner/support owners and close through the
[master](../Fixture-Execution-Plan.md). This supplies no customer/E2E acceptance.
