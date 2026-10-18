# 002c — Run the complete Ubuntu upgrade history

Acceptance: installed
Targets: onpc-Ubuntu26.04

Requires: 002b.

## Scope and prerequisites

Qualify only Ubuntu's complete case 287, preserving every requirement in
[003](003-previous-package-upgrade.md). Read the
[VM mandate](../../Mandates/VM-Mandate.MD), the installed runner's
[earlier-release route](../../../tests/integration/README.md#running-the-current-installed-suite),
and [retained evidence](../Core-Installation-Coverage-Handoff.md#task-003-retained-work-and-fixture-prerequisite).
Verify accepted preparation contains 002a's trusted variants and the staged
consumer includes 002b. Prepare missing verified current/previous inputs through
`tools/run-tests artifacts prepare --for-vm --upgrade-inputs --vm 'onpc-Ubuntu26.04'`.
Use the returned directories immediately; never fabricate a previous version.

## Acceptance and close-out

Run registered `test_previous_package_policy_preservation` (ID 287) through the
existing `--previous-artifacts` route. Keep `previous-policy`, `installed` and
`rebooted` in one owned attempt, with no intermediate restore. Require the
37-minute daily allowance, hard/soft choices, 23-minute request choice, real
authenticated twelve-hour addition, exact grant issuance/expiry with decreasing
balance, schema 3 → 4, kiosk shell transition with other identity preserved,
retirement/refusal gates, public broker recovery, native hard denial/approved
soft allowance and unrelated-user controls. Service-active alone cannot pass.

Retain all three passing phase JUnits, versions/source/package/input/baseline
bindings, independent product/infrastructure/collection/cleanup results and
baseline restoration/off evidence. Let recording and cleanup finish. Use the
[report retention contract](../../../tests/README.md#aggregate-output-retention)
to keep evidence through 003 close-out. A final helper/input change requires
rerunning the complete affected history. Diagnose a failure without weakening
assertions; independent missing work needs a bounded prerequisite.

Mark only 002c complete, record its exact receipt in the master/queue and advance
the pointer. Leave 003 unchecked and customer E2E untouched. The 30–45 minute
estimate allows the indivisible install/update/reboot history and owned cleanup.
