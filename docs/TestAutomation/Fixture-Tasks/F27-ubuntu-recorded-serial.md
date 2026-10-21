# F27 — Integrate Ubuntu recorded serial preparation

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F26

## Scope and implementation

Migrate the recorded serial E2E [matrix row](../Fixture-Design.md#runner-acceptance-matrix).
Read `serial_harness.record_serial_journey`, `execution.ScenarioContext`, recorder
setup/worker ownership and F01's exact preparation binding. Use the shared SSH
provisioner after transport readiness and before serial worker input. Preserve
the recorder's setup/start boundary, credential/getty lifetime and private seals.
This is a distinct caller from standalone `check_graphical_smoke.Smoke.execute`.

## Finite acceptance

Run affected host fixture/recorder/provenance/cleanup checks. Register/list the
planned binding before
`tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_recorded_serial`.
Invoke the real recorded harness preparation through fixture readiness and
independently read/execute a harmless fixture witness over owned SSH. Stop before
serial input or any product action/assertion. Prove a fresh receipt, unchanged
attempt pin under a host edit, missing/stale refusal without input and recorder
provenance bound to the exact pin. Host composition checks preserve the original
serial/secret guards without requalifying authentication or customer behavior.
Finish watched restoration, credentials/transport/pins and recorder cleanup,
update delivered owners and close through the [master](../Fixture-Execution-Plan.md).
