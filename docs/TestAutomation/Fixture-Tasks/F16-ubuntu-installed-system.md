# F16 — Integrate Ubuntu installed-system preparation

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F10

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate `system_snapshots._run_attempts(installed=True)` through
`Suite.prepare_case`, explicit offline app-snapshot restoration/bootstrap and
`system_runner.installed_run`. Read the full shared input/provisioning chain.
Suite currently defaults online; establish the explicit offline binding rather
than assuming it exists. Preserve the installed product/precondition and every
system assertion.

Reuse the execution-owned immutable input and single SSH provisioner on clean
captures. Bind readiness to the actual restored/rebound boot and attempt.
Enable only this qualified target/branch; other unmigrated branches must refuse.
Keep platform-specific corrections in their shared owning adapter.

## Acceptance and cleanup

Run exact affected host composition/provenance/ownership safety selections.
Register/list the planned `check_fixture_system_installed` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Ubuntu26.04' check_fixture_system_installed
```

Use the trusted-native hard witness as Riley after actual offline restore.
Stop before system input or product assertions. Host tests cover aliases and
reboot readiness renewal; an online result does not qualify this branch.
Prove selected manifest bytes independently, positive runtime use, fresh readiness,
missing/incompatible refusal before input and no version switch under host edits.
No complete fixture collection is copied into results; preserve scenario mutations.
Finish watched owned restoration and credential/staging/input/transport cleanup.
Update delivered runner/support owners and close through the
[master](../Fixture-Execution-Plan.md). This supplies no customer/E2E acceptance.
