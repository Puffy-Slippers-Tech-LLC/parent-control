# C04i — Renew existing kiosk About coverage

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C04c.
Estimate: 20–30 min.

Apply the [master contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

Reuse B3's existing installed kiosk About/return slice from the
[finite recipe](../TestAutomation/E2E-Scenario-Recipes.md#baseline-inputs-and-public-results).
`restricted_station_about.PLAN` / `check_e2e_read_restricted_station_about`.
Independently read installed product/version, external-action absence and the
unchanged usable request after ordinary About close. Tasks 185k/234 recorded
installed qualification and case 192 acceptance; task 192's host metadata
exception is unrelated. Check applicability and renew only affected caller scope.

New What's New content automation belongs to
[E2E task 315](../TestAutomation/E2E-Tasks/315-kiosk-whats-new.md) and does not
block confinement baseline readiness. No external navigation, release-note
translation sync or visual comparison belongs here.

Read `tests/e2e/kiosk_about.py`, its shared `AccessibleUI` information operations,
the relevant public-ID inventory in
[Application UI API](../TestAutomation/Application-UI-API.md), and actual packaged
About source reached through [Front ends](../SystemDesign/Frontends.md).
Reuse the shared information/return operations; add no general feature binding.

No new baseline information qualifier is required. Reuse valid evidence; when
renewal is needed, run affected host information/return checks with finite timeouts
and
`tools/run-tests --vm 'onpc-Ubuntu26.04,onpc-Fedora44' integration 'check_e2e_read_restricted_station_about'`.
Keep 1800-second attempts and 90-second kiosk observations. Retain exact installed
package/content identity, meaningful information reads and unchanged return,
then full collection and owned baseline restoration. Update this catalogue scope
without granting broader case or C05 acceptance.
