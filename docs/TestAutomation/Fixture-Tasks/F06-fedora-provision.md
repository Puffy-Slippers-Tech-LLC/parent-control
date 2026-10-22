# F06 — Qualify Fedora fixture provisioning

Acceptance: installed
Targets: onpc-Fedora44
Requires: F12

## Scope and implementation

Qualify [shared provisioning](../Fixture-Design.md#owned-ssh-provisioning-and-readiness)
on F12's clean Fedora captures. Read the full F05/F15 chain and existing Fedora
native trust/admission and SELinux labeling operations. Keep generic mechanics
shared; isolate only evidenced platform behavior.

## Acceptance and cleanup

Run affected isolated safety tests, register/list `check_fixture_provisioning`
for this target, and repeat F05's finite positive/no-op/refusal/interruption
history under watched ownership. Independently prove selected bytes/metadata,
harmless runtime use, enforcing SELinux, exact native activation and deliberately
untrusted controls. Preserve vendor trust and product rules; broad directory trust
or disabled enforcement fails. Failed/uncertain work must withhold all input and
complete existing VM recovery. A fresh attempt must provision successfully.
Complete staging/transport/VM cleanup, renew affected Ubuntu proof after shared
fixes and update delivered target/support owners. Other envelopes remain gated.

Follow the [master](../Fixture-Execution-Plan.md) for reading, resource review,
owned cleanup and ordinary evidence/Git close-out.
