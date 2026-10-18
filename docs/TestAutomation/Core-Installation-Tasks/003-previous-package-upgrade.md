# 003 — Qualify a real earlier-package upgrade

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and scope

Use a genuinely earlier supported product package, not the current candidate
reinstalled. Qualify saved policy, migration/exclusion and admission retirement
through native update and required reboot. Existing `--previous-artifacts`
support installs and reboots the old package and verifies retirement/activation.
Case 287 now adds prior child policy and an active grant with qualified trusted
fixtures; its final installed qualification remains unfinished. Extend that route rather
than building another one.

## Prerequisites and task boundary

Requires: 002, 002a, 002b, 002c.

[002b](../Core-Installation-Coverage-Handoff.md#task-002b-qualified-fixture-integration)
delivered consumer integration and focused host checks.
[002c](002c-upgrade-histories.md) owns the complete Ubuntu and Fedora
histories, scheduled in parallel with independent ownership and evidence.
This row retains every original requirement below and
accepts only both matching target results. It owns final evidence reconciliation
and close-out, not another implementation pass or mandatory duplicate live run.
Reuse those complete receipts only while their exact candidate, helpers, selected
inputs, baselines and assertions still match. Rerun an invalidated history in
full; an older partial result cannot fill a missing phase.

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
Inspect `system_previous_upgrade.prepare`/`witness_enforcement`/
`verify_updated`/`verify_reboot`, `system_runner.stage_upgrade_assets`/`installed_run`,
`system_guest.install_previous`/`upgrade`/`verify_upgrade_admission_receipt`,
`build_test_artifacts.verify_upgrade` and their existing host regressions.

Prepare verified prior DEB/RPM artifacts using maintained builders. Record the
chosen source revision, package version, architecture and digests, and require
that the old version differs from the candidate. Missing buildable earlier
artifacts are a concrete blocker, never grounds to substitute a reinstall.
Preserve the implemented pre-upgrade checkpoint through the existing runner,
which establishes non-default child allowance, hard/soft policy and an unexpired
grant using supported product interfaces. Do not preseed those in the baseline.

Registered selector: `test_previous_package_policy_preservation` (system ID 287).
Its `previous-policy`, `installed` and `rebooted` phases are one owned history;
use the [installed runner's verified earlier-release route](../../../tests/integration/README.md#running-the-current-installed-suite).
Select a supported prior release covering the admission protocol transition
when available; explicitly record the chosen compatibility boundary.

The finite state is a 37-minute daily allowance, a permanent hard app rule,
a conditional soft app rule, a custom 23-minute request choice and a real
authenticated fixed request for twelve additional hours. The grant's exact issuance and duration
survive update/reboot; elapsed wall-clock time reduces remaining time, including
across midnight, under [grant arithmetic](../../SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities).

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

## Qualified fixture prerequisite 002a

[002a is qualified](../Core-Installation-Coverage-Handoff.md#task-002a-trusted-native-fixture-qualification)
on both targets. Select its baseline-owned `trusted-hard` and `trusted-soft`
variants through the existing closed enforcement interfaces when resuming this
consumer. The [master's retained work](../Core-Installation-Coverage-Handoff.md#task-003-retained-work-and-fixture-prerequisite)
records the implementation, exact prior inputs, Ubuntu's earlier 3/3 slice,
Fedora's repeated failure/compiled policy and completed cleanup. Fedora's old
default policy denies the current untrusted native fixture for the unrelated
user. Preserve every policy, grant, unrelated-user and admission-retirement
assertion when selecting the qualified inputs. This input qualification grants
no upgrade acceptance and establishes no current-candidate product defect.
Requalify both full histories after the final fixture/baseline
change; retained earlier phases cannot substitute for that work. Keep this row
unchecked until every original installed requirement and cleanup passes.
