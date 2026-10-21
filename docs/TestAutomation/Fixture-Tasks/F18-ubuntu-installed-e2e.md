# F18 — Integrate Ubuntu installed E2E preparation

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F17

## Scope and implementation

Migrate the installed E2E row of the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix).
Read `InstalledJourney` setup, `installed_setup.py`, `AssetTransfer.provision_installed`,
`online_snapshot` credential rebind, native fixture readers, private artifact
staging and F01's exact binding. Reuse the common host pin/provisioner after the
owned online snapshot resumes and transport is rebound, before worker/customer
input. Keep scenarios/assertions and qualified UI operations unchanged. Aliases
must be mapped by real host branch tests, not by matching their names.

## Finite acceptance

Run affected host ownership/transport/provenance checks. Register/list the planned
binding before
`tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_e2e_installed`.
Invoke the real installed E2E preparation through online resume/rebind and
independently read/execute a harmless fixture witness over SSH. Stop before E2E
worker/customer input or product assertions. Prove missing/stale inputs stop before worker input,
saved receipts cannot satisfy the new attempt, host edits retain the pin and
scenario-owned state is unchanged. Cover reboot renewal and installed-qualifier
aliases at the shared owner. Preserve one positive use plus the required input
refusal history within fixture infrastructure. Finish watched cleanup and pin release,
update delivered owners and close through the [master](../Fixture-Execution-Plan.md).
