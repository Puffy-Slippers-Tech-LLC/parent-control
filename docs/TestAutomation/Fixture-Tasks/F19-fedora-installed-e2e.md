# F19 — Integrate Fedora installed E2E preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F18

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate `InstalledJourney`/`InstalledSetup.provision` and
`AssetTransfer.provision_installed` after online app-snapshot resume and credential
rebind, before worker input. Read complete native/artifact/online setup callers.
Host composition evaluates each wrapper's final ordered `qualification_class`,
including loop alternatives and explicit offline restore. A different preparation
branch needs its own proof. Preserve qualified UI operations and scenario state.

Reuse the execution-owned immutable input and single SSH provisioner on clean
captures. Bind readiness to the actual restored/rebound boot and attempt.
Enable only this qualified target/branch; other unmigrated branches must refuse.
Preserve enforcing SELinux, exact native admissions and labels. Renew affected
Ubuntu checks after shared corrections.

## Acceptance and cleanup

Run exact affected host composition/provenance/ownership safety selections.
Register/list the planned `check_fixture_e2e_installed` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_e2e_installed
```

Exercise actual online resume/rebind and harmless native use over SSH.
Cover the mapped offline qualification alternatives at their shared owner;
host coverage may share a live result only for the exact qualified branch.
Stop before E2E worker input or product assertions.
Prove selected manifest bytes independently, positive runtime use, fresh readiness,
missing/incompatible refusal before input and no version switch under host edits.
No complete fixture collection is copied into results; preserve scenario mutations.
Finish watched owned restoration and credential/staging/input/transport cleanup.
Update delivered runner/support owners and close through the
[master](../Fixture-Execution-Plan.md). This supplies no customer/E2E acceptance.
