# F28 — Integrate Fedora recorded serial preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F27

## Scope and implementation

Qualify the recorded serial E2E [matrix row](../Fixture-Design.md#runner-acceptance-matrix)
on Fedora. Read F27's complete preparation/recorder chain, F01's Fedora binding
and native labels/trust. Reuse the SSH/pin/receipt owner; preserve serial-recipient
guards, private seals, recorder steps and enforcing SELinux.

## Finite acceptance

Run affected isolated fixture safety checks and register/list the planned binding
before `tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_recorded_serial`.
Invoke the actual recorded preparation only, prove selected fixture use over SSH,
correct trust/labels, renewed boot/attempt receipt, immutable pin under a host
edit, missing/stale refusal without input and exact recorder provenance. Stop
before serial input or product actions/assertions. Finish watched restoration and
credential/transport/pin/recorder cleanup, renew affected Ubuntu infrastructure
proof after shared fixes and update owners through the [master](../Fixture-Execution-Plan.md).
