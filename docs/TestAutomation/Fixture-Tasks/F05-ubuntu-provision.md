# F05 — Qualify Ubuntu fixture provisioning

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F11

## Scope and implementation

Qualify [shared provisioning](../Fixture-Design.md#owned-ssh-provisioning-and-readiness)
against F11's clean Ubuntu captures. Read the complete F15 transport/native/
ownership/cleanup chain and the declared subsets. Reuse one provisioner; no
parallel installer or snapshot-embedded fallback. Keep ordinary unqualified
runner branches gated.

## Acceptance and cleanup

Run affected isolated fixture/transport/trust/cleanup regressions first.
Register/list `check_fixture_provisioning`, then invoke it through the maintained
integration launcher on this target. In watched owned attempts prove first/minimal
transfer, repeated verification without writes, selected native/activity/trusted
runtime use, exact native activation and intentionally untrusted controls.
Read bytes, owners/modes and actual attempt/boot independently.

Cover missing/corrupt/incompatible input, foreign destinations, interrupted
transfer/activation and lost replies. Host injection covers unsafe fault cases.
Failure must release no scenario input and complete normal owned VM recovery;
a fresh clean attempt provisions successfully. Changing subsets uses a fresh
attempt, not in-place contraction. Preserve unrelated state, vendor trust and
product policy; no directory trust or dependency installation. Update delivered
support/environment owners after complete staging, transport and VM cleanup.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
