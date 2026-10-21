# F26 — Integrate Fedora serial qualification

Acceptance: installed
Targets: onpc-Fedora44
Requires: F25

## Scope and implementation

Qualify F25's standalone serial [matrix row](../Fixture-Design.md#runner-acceptance-matrix)
on Fedora. Read its full getty/credential/bootstrap/provisioning chain, F01's
binding and native labels/trust. Preserve preboot credential lifetime, recording
seals and input recipients while fixture bytes move through the same owned SSH API.

## Finite acceptance

Run affected host safety checks and register/list the planned binding before
`tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_serial`.
Use the actual serial qualification preparation to prove selected harmless fixture
use over SSH before serial input, immutable pin, correct trust/labels, fresh boot receipt and
missing/stale refusal without input. Validate authenticated-install/refusal alias
composition with host checks preserving secret-recipient guards. Stop before
serial input, authentication or product actions/assertions. Finish watched
restoration and credential/transport/pin cleanup, renew Ubuntu proof invalidated
by shared changes and update delivered owners through the [master](../Fixture-Execution-Plan.md).
