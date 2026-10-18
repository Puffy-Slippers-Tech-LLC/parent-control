# 002c — Run the complete Ubuntu and Fedora upgrade histories

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Requires: 002b.

## Scope and prerequisites

Qualify complete case 287 on both targets, preserving every requirement in
[003](003-previous-package-upgrade.md). Read the
[VM mandate](../../Mandates/VM-Mandate.MD), the installed runner's
[earlier-release route](../../../tests/integration/README.md#running-the-current-installed-suite),
and [retained evidence](../Core-Installation-Coverage-Handoff.md#task-003-retained-work-and-fixture-prerequisite).
Verify accepted preparation contains 002a's trusted variants and the staged
consumer matches [002b's final helper/input requirements](../Core-Installation-Coverage-Handoff.md#task-002b-qualified-fixture-integration).
Prepare missing verified current/previous inputs for each target through
`tools/run-tests artifacts prepare --for-vm --upgrade-inputs --vm NAME`.
Use each target's returned directories immediately; never fabricate a previous
version. Require genuinely earlier DEB/RPM versions under native ordering.

Schedule the two independent target histories in parallel through maintained
runner routes, within the registry concurrency cap and with separate leases,
target-specific inputs and evidence. There is no Ubuntu-before-Fedora dependency.
Keep phases ordered within each VM. Separate diagnosis into a target-specific
prerequisite only when evidence establishes an issue unique to that VM; shared
helper/input work stays shared.

## Acceptance and close-out

Run registered `test_previous_package_policy_preservation` (ID 287) through the
existing `--previous-artifacts` route. Keep `previous-policy`, `installed` and
`rebooted` in one owned attempt, with no intermediate restore. Require the
37-minute daily allowance, hard/soft choices, 23-minute request choice, real
authenticated twelve-hour addition, exact grant issuance/expiry with decreasing
balance, kiosk shell transition with other identity preserved,
retirement/refusal gates, public broker recovery, native hard denial/approved
soft allowance and unrelated-user controls. Require schema 3 → 4 on Ubuntu and
4 → 4 on Fedora. Service-active alone cannot pass. Fedora's earlier
untrusted-fixture failure occurred before candidate installation; preserve the
unrelated-user positive control and do not claim that failure as a candidate defect.

For each target, retain all three passing phase JUnits, exact version/source/
package/input/baseline bindings, independent product/infrastructure/collection/cleanup results and
baseline restoration/off evidence. Let recording and cleanup finish. Use the
[report retention contract](../../../tests/README.md#aggregate-output-retention)
to keep evidence through 003 close-out. A final helper/input change requires
rerunning every complete affected target history, including an already passing
sibling if its evidence was invalidated. Diagnose a failure without weakening
assertions; independent missing work needs a bounded prerequisite.

Mark only 002c complete after both targets pass, record their exact receipts in
the master/queue and advance to 003. Retain a valid complete target result if its
sibling fails; rerun only failed or invalidated complete histories. Leave 003
unchecked and customer E2E untouched. The 30–45 minute estimate allows parallel
indivisible install/update/reboot histories and owned cleanup; a lower concurrency
cap can increase wall time.
