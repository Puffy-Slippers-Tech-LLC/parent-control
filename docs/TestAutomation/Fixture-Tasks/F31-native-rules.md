# F31 — Render and decode finite fixture native rules

Acceptance: host
Requires: F30

## Scope and implementation

Implement the rule renderer and attributed-decision decoder for the
[native protocol](../Fixture-Design.md#fixture-only-native-acknowledgement-protocol).
Read native_assets/native_trust, baseline native inventories, guest native readers
and the existing acknowledgement limits. Generate only finite UID/path/hash
barriers, nonce startup controls and unique-executable/PID/UID observer rules.
Handle whitespace/comma destinations through exact content identities, including
their documented identical-copy effect. Preserve all non-fixture rule bytes.

Decode only required typed decision fields from the current service invocation
after the recorded cursor. Bind rule position to the exact compiled-input map,
permission, tracee identity, input and expected trust. Log absence, ambiguity or
unsupported fields refuses; disk freshness and notification success are not
activation receipts. This task implements pure rendering/validation; F50 owns
the transition state machine and F32 supplies owned probes.

## Finite validation and cleanup

Use private rule/log inputs for both native layouts, path grammar, UID sets,
trust=0/1, stale cursor/invocation, wrong rule/permission/path/PID and malformed/
missing records. Ensure a generic deny or early marker cannot pass a transition.
Run exact scoped native/fixture unit safety selectors. No host native policy,
daemon or VM is operated. Update support contracts and close through the
[master](../Fixture-Execution-Plan.md).
