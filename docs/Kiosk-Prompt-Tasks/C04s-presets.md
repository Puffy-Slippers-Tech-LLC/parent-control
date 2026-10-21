# C04s — Reuse existing request-choice coverage

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C04c.
Estimate: 20–30 min.

Apply the [master contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

Reuse B3's existing request-choice coverage from the
[finite recipe](../TestAutomation/E2E-Scenario-Recipes.md#baseline-inputs-and-public-results),
using `kiosk_valid_duration.PLAN` / `check_e2e_kiosk_valid_duration` delivered by
E2E 012c: 5-minute preset, Rest of day, Custom `1.25` Minutes/75 seconds, soft
inclusion/exclusion, independent estimates and Cancel/GDM return. Keep its
existing inputs; do not invent a zero-daily variant just for feature renewal.
Reentry/remembered choices reuse task 014's exact shared operation.

New saved-preset addition/deletion and Hours automation belong to
[E2E task 314](../TestAutomation/E2E-Tasks/314-request-presets.md), outside this
baseline's prerequisites. Existing host UI coverage remains with its owner.

Read `tests/e2e/request_choices.py`, `request_flow.py`, `allowance_presets.py`
(Parent allowance is a distinct operation), the relevant complete request
methods in `tests/e2e/accessible_ui.py`, and their shared worker route.
Review retained exact evidence and renew only invalidated kiosk caller scope;
general feature API extensions do not belong to this task.

No new baseline preset qualifier is required. Reuse valid evidence; when renewal
is needed, run affected host request/composition checks with finite timeouts and
`tools/run-tests --vm 'onpc-Ubuntu26.04,onpc-Fedora44' integration 'check_e2e_kiosk_valid_duration'`.
Keep each 1800-second attempt and 90-second kiosk observations. No authentication
or downstream access claim belongs to this slice. Retain exact candidate/input
and saved-result evidence, public restoration and owned baseline cleanup.
Update only this exact catalogue scope; preserve stable cases and C05 acceptance.
