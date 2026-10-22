# F05 — Qualify Ubuntu fixture provisioning

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F11, F53

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

## Resume after F53

The selector `check_fixture_provisioning` is registered, with its caller-owned
input selected before privileged dispatch. Its three planned live attempts are
foreign-destination refusal, fresh minimal trusted-hard provisioning and an
installed native/activity/trusted union. None has passed installed acceptance.
F53 repaired and qualified the native environment prerequisite through the
[clean snapshot owner](../../../tests/integration/Environment.md#ubuntu-clean-snapshots).
Both restored captures passed active-service and read-only database checks,
preserved all original vendor trust and remained fixture-free. Resume F05 against
those captures; preserve every assertion above. F53 supplies no provisioning credit.

F53's retained acceptance and cleanup are linked from the
[queue](../Fixture-Task-Queue.md). The earlier affected F05 host run
reported 2,579 checks passed; its short-lived report has since rotated under
ordinary retention, so it supplies no retained detailed proof.
`make build` passed for DEB and RPM after the storage change. Independent Sol High
review resolved owned-build cancellation and input lifetime findings; the narrow
output-ancestor permission repair was also reviewed without actionable findings.
Standalone-launcher import and early-error diagnostics were repaired and tested.
These checks supply no installed credit. All helpers finished; owned producer,
transport and VM cleanup ended, with the VM restored off.
