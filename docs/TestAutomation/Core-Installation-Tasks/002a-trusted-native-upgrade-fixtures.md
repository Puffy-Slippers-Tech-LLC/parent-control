# 002a — Prepare trusted native upgrade fixtures

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and prerequisite

Requires: 002.

Supply native application witnesses which the pinned earlier packages can run
for an unrestricted user without weakening distribution security policy.
Task 003's retained [diagnosis](../Core-Installation-Coverage-Handoff.md#task-003-retained-work-and-fixture-prerequisite)
shows Fedora v1.3's native trusted-file allow and default execute denial preceding
its product fallback. Existing root-owned fixture copies are untrusted; that
is unsuitable for the upgrade history's unrelated-user positive control.
This new row suspends 003 and grants it no acceptance credit.

## Reading and implementation route

Follow [execution plans](../../Execution-Plans.md), the
[VM mandate](../../Mandates/VM-Mandate.MD),
[test storage](../../Mandates/Test-Storage-Mandate.md),
[installed environment](../../../tests/integration/Environment.md) and
[fixture/support ownership](../../../tests/support/README.md).
Inspect the complete relevant functions in `tests/fixtures/baseline_assets.py`,
`tests/fixtures/build_test_applications.py`,
`tests/integration/baseline_fixtures.py`, `baseline_guest.py`,
`prepare_baseline.py`, `prepare_vm.py`, `system_enforcement.py` and their existing
host regressions. Reuse the artifact builder's pinned v1.2 DEB / v1.3 RPM sources
and the installed runner's guarded installation/boot mechanics.

Add a finite pair of independently named trusted native fixture variants for
hard/soft policy witnesses. Preserve the existing untrusted variants and every
existing case's input/expectation. Use maintained native packaging/trust APIs
and exact payload identities; being root-owned is not proof of native trust.
Do not add an unrestricted allow rule, disable security enforcement, trust a
directory, rewrite a prior product release or change expected execution results.
Reusable placement and trust provenance belong to the public `tools/prepare-vm`
route and its baseline record, never opportunistic repair inside a test.
Preserve product-free baseline capture and do not seed child policy/grants.
Refuse foreign/substituted inputs and cover interrupted reconciliation/retry.

Expose the new variants through the existing closed fixture/probe interfaces.
Consumers must verify their bytes, metadata, native package/trust provenance
and baseline binding. Keep readiness/output and directly owned-process cleanup
guards. Task 003 will select these qualified inputs when resumed, retaining all
of its policy, grant, unrelated-user and admission-retirement assertions.

Planned fixture qualification selector: `test_trusted_native_upgrade_fixtures`
(unimplemented). Register its bounded old-package install/boot/native-control
history before execution. It qualifies the input, not the candidate upgrade;
do not execute or close task 003 as part of this prerequisite.

## Acceptance, cleanup and close-out

Run focused host fixture/provenance/refusal/retry, runner and resource-inventory
regressions. Refresh each required baseline through authorized auto preparation
when its new fixture record requires it; preserve leases, watch and UUID pins.
Automatically prepare missing generated package inputs through maintained routes.

On both named targets, install and boot the exact pinned earlier package in one
owned attempt. Independently verify the fixture's native trust and actual
unrestricted execution for both fixed child/other roles. Through supported old
broker operations, verify child-only hard denial, strict soft denial, real
authenticated soft approval and unrelated-user execution with the same trusted
bytes. Keep the existing untrusted fixture's identity and expected trust state
unchanged. Retain native versions/digests, effective rules and passing JUnits
without skips. No GUI customer journey or new product behavior is required.

Finish all owned processes, VM restoration, independent baseline verification,
recording finalization and powered-off checks. Review applicable scheduling
inventories, refresh generated coverage and Markdown links, and run the owning
documentation checks. Follow the build contract if build inputs change.
After both target qualifications and cleanup pass, check only 002a, record its
concise evidence in the master/queue, remove this brief and return the master
pointer to still-unchecked 003. Preserve 003/004's original scope and Requires;
003 must then run both complete matching upgrade histories independently.
