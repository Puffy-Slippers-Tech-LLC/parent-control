# F17 — Integrate Fedora installed-system preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F16

## Scope and implementation

Qualify the installed-system row of the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix)
on Fedora. Read F16's complete offline restore/bootstrap/provisioning chain,
F01's Fedora binding and native trust/label actions. Use the same host pin and
shared API; preserve installed product/system assertions and enforcing SELinux.

## Finite acceptance

Run affected host safety checks and register/list the planned engineering binding
before `tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_system_installed`.
Invoke F01's installed-system preparation through actual offline app restoration,
read/execute a harmless fixture witness over SSH and stop before system test or
product actions/assertions.
Prove selected runtime use, correct trust/labels, fresh attempt/boot receipts,
missing/incompatible refusal before test input, no host-version switch and no
full fixture cache copy in results. Complete watched restoration and release
transport/pins only after cleanup proof. Renew Ubuntu proof invalidated by shared
changes, update delivered owners and close through the [master](../Fixture-Execution-Plan.md).
