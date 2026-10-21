# F25 — Integrate Ubuntu serial qualification

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F23

## Scope and implementation

Migrate the standalone serial [matrix row](../Fixture-Design.md#runner-acceptance-matrix).
Read `check_graphical_smoke.Smoke.execute`, `check_graphical_serial`, authenticated
install/refusal aliases, getty/credential staging and F01's exact consumer map.
Keep transport/credential bootstrap and fixed getty preparation at their required
preboot boundary, while fixture bytes use owned SSH before any serial/customer
input. Share the same pin/provisioner; preserve guarded secret recipients, recording
seals, single-use input and deliberate package installation checkpoints.
Recorded serial E2E callbacks retain their explicit legacy gate until F27/F28.

## Finite acceptance

Run affected host serial/credential/transfer safety checks. Register/list the
planned binding before
`tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_serial`.
Exercise the actual `check_graphical_serial` preparation with the shared provisioner,
one immutable pin, fresh receipt and independently observed harmless fixture use
over SSH. Stop before serial input or product actions/assertions. Prove missing/
stale fixture refusal releases no input. Host branch
tests bind authenticated-install/refusal aliases to this same preparation;
different fixture branches require a separate preparation-only prerequisite.
Host checks preserve privacy/recipient guards without requalifying serial login,
authentication or package behavior. Finish watched restoration, credential/transport/pin
cleanup, update delivered owners and close through the [master](../Fixture-Execution-Plan.md).
