# 003 — Qualify a real earlier-package upgrade

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and scope

Use a genuinely earlier supported product package, not the current candidate
reinstalled. Qualify saved policy, migration/exclusion and admission retirement
through native update and required reboot. Existing `--previous-artifacts`
support installs and reboots the old package and verifies retirement/activation,
but does not by itself establish preservation of meaningful prior child policy
or an active grant/session. Extend that route rather than building another one.

Customer update journeys remain pending under tasks 135a–140 in the
[existing E2E queue](../E2E-Task-Queue.md). This engineering task grants no customer
journey acceptance and must not duplicate their GUI obligations.

## Reading and implementation route

Read the [master](../Core-Installation-Coverage-Handoff.md),
[Lifecycle](../../SystemDesign/Lifecycle.md),
[Data Migration](../../SystemDesign/Data-Migration.md),
[Kiosk Confinement](../../SystemDesign/Kiosk-Confinement.md),
[installed runner](../../../tests/integration/README.md),
[VM mandate](../../Mandates/VM-Mandate.MD) and affected test-support contracts.
Inspect `system_runner.stage_upgrade_assets`/`installed_run`,
`system_guest.install_previous`/`upgrade`/`verify_upgrade_admission_receipt`,
`build_test_artifacts.verify_upgrade` and their existing host regressions.

Prepare verified prior DEB/RPM artifacts using maintained builders. Record the
chosen source revision, package version, architecture and digests, and require
that the old version differs from the candidate. Missing buildable earlier
artifacts are a concrete blocker, never grounds to substitute a reinstall.
Add a bounded pre-upgrade scenario checkpoint through the existing runner to
establish non-default child allowance, hard/soft policy and an unexpired grant
using supported product interfaces. Do not preseed those in the baseline.

Planned selector: `test_previous_package_policy_preservation` (unimplemented).
Register its full history before using the existing `--previous-artifacts` option.
Select a supported prior release covering the admission protocol transition
when available; explicitly record the chosen compatibility boundary.

## Acceptance and close-out

Run focused host ownership/provenance/history regressions, then the registered
upgrade history on both targets. Independently verify old installation and boot,
non-default state before update, package version change, blocked unsafe
activation/removal before required retirement, and preserved policy/identity
after update/reboot. Define exact time/grant survival expectations from the
owning product contract before asserting them. Verify the broker's public
operation and real native allow/deny enforcement after recovery, plus unrelated
user preservation; service-active alone is insufficient.

Keep this complete history in one owned attempt; restore only during normal
cleanup. Retain both target receipts and cleanup. Run `make build` after product
edits, refresh generated inventory/links, close only this engineering row and
advance the master. Do not close customer E2E tasks from this evidence.
