# F16 — Integrate Ubuntu installed-system preparation

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F10

## Scope and implementation

Migrate the installed-system row of the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix).
Read F09's shared preparation API, `system_snapshots._run_attempts(installed=True)`,
`Suite.prepare_case`, offline snapshot/bootstrap, `system_runner.installed_run`
and F01's exact binding. Reuse the host pin, authenticated reader and shared
provisioner after app-snapshot restore/SSH readiness, before installed test input.
Preserve the offline installed starting state, product identity and system
assertions. Other unqualified envelopes retain their legacy gates.

## Finite acceptance

Run affected host envelope/provenance/recovery safety tests. Register/list the
planned `check_fixture_system_installed` engineering binding, then invoke
`tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_system_installed`.
Exercise its real preparation through offline app restore, then independently
read/execute a harmless fixture witness over SSH. Stop before system test/product
actions or assertions. Prove selected bytes are used, stale/missing inputs stop before test
input, restored receipts are renewed, host edits do not switch the attempt pin,
and product/baseline identities remain intact. Host branch tests cover aliases
and reboot receipt renewal. Complete watched owned restoration, transport and
pin cleanup; update delivered system/support/provenance owners and close through
the [master](../Fixture-Execution-Plan.md).
