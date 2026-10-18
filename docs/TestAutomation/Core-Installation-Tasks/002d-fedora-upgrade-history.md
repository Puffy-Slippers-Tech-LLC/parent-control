# 002d — Run the complete Fedora upgrade history

Acceptance: installed
Targets: onpc-Fedora44

Requires: 002b, 002c.

## Scope and prerequisites

Qualify only Fedora's complete case 287 against all requirements in
[003](003-previous-package-upgrade.md). Read the
[VM mandate](../../Mandates/VM-Mandate.MD), the installed runner's
[earlier-release route](../../../tests/integration/README.md#running-the-current-installed-suite),
and the [retained diagnosis](../Core-Installation-Coverage-Handoff.md#task-003-retained-work-and-fixture-prerequisite).
Verify 002a's accepted trusted baseline variants and
[002b's final helper/input requirements](../Core-Installation-Coverage-Handoff.md#task-002b-qualified-fixture-integration).
Prepare missing inputs through
`tools/run-tests artifacts prepare --for-vm --upgrade-inputs --vm 'onpc-Fedora44'`
and use the returned current/previous directories immediately. The pinned RPM
must remain genuinely earlier under native version ordering.

## Acceptance and close-out

Run registered `test_previous_package_policy_preservation` (ID 287) through the
existing `--previous-artifacts` route, all three phases in one owned attempt.
Preserve every 003 assertion: meaningful policy/request choices, real approved
grant with exact issuance/expiry and decreasing balance, schema 4 → 4, kiosk
shell transition/identity, retirement and reboot gates, public broker recovery,
native hard denial, approved soft allowance and unrelated-user execution.
The previous untrusted-fixture failure occurred before candidate installation;
do not remove that positive control or claim it as a candidate defect.

Retain passing phase JUnits, exact package/source/input/baseline bindings and
independent product/infrastructure/collection/cleanup results. Finish recording,
baseline restoration and off verification; preserve evidence through 003 under
the [retention contract](../../../tests/README.md#aggregate-output-retention).
Never splice older phases or restore inside the history. If diagnosis changes
shared helpers, inputs or requirements, identify any invalidated Ubuntu history
and rerun it completely before final 003 acceptance.

Mark only 002d complete and advance to 003; record exact evidence in the existing
master/queue. No customer E2E completion. The 30–45 minute estimate covers one
indivisible live history and cleanup, not additional implementation.
