# F10 — Integrate Fedora product-free system preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F09

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Migrate the product-free system branch through
`system_snapshots._run_attempts(installed=False)` and
`system_runner.installed_run(already_installed=False)`. Read complete artifact/
named-input and attempt preparation callers. Preserve lifecycle/history,
first-configure/PAM and `fresh_install` dispatch and previous-package requirements.
Factor the same boundary for `check_parent_setup`, `check_parent_input` and
`check_parent_standard_input` after `Transport.probe_ready`, before
`InstalledSetup.run`. All three aliases need host composition coverage.

Reuse the execution-owned immutable input and single SSH provisioner on clean
captures. Bind readiness to the actual restored/rebound boot and attempt.
Enable only this qualified target/branch; other unmigrated branches must refuse.
Preserve enforcing SELinux, exact native admissions and labels. Renew affected
Ubuntu checks after shared corrections.

## Acceptance and cleanup

Run exact affected host composition/provenance/ownership safety selections.
Register/list the planned `check_fixture_system_product_free` before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_system_product_free
```

Use the selected trusted-native hard witness as Riley, with no desktop file.
Observe product absence and stop before installation input or any system phase.
No installed-snapshot result substitutes for this bootstrap branch.
Prove selected manifest bytes independently, positive runtime use, fresh readiness,
missing/incompatible refusal before input and no version switch under host edits.
No complete fixture collection is copied into results; preserve scenario mutations.
Finish watched owned restoration and credential/staging/input/transport cleanup.
Update delivered runner/support owners and close through the
[master](../Fixture-Execution-Plan.md). This supplies no customer/E2E acceptance.
