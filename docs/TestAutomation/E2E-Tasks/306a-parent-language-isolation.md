# 306a — Qualify Parent language across child selection

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300g** — Parent public language selection and relaunch.
- **300j** — Language-aware child identity/readback and independent kiosk choices.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify one Parent binding: Jamie's product language `zh-Hans`, with Riley
and Jordan independently selected through public controls. Prepare each child's
declared enabled allowance in English, capture public settings/app rows and
zero grant, then save Chinese through LANG01. Select Riley → Jordan → Riley;
independently require each UID, unchanged account/application names, the same
Chinese management text and Jamie's checked choice. Reopen Parent normally and
repeat the read without first-run setup. Compare each child's own policy and
numeric values, allowing only explicitly bounded real elapsed time.

The existing `parent_language_state` qualification assumes disabled limits and
zero allowance. Extend its shared observation contract for this enabled-state
binding; never use the English-only policy reader to claim Chinese readback.
Reject wrong account/page, mixed or missing text, stale selection and uncertain
input without replay.

## Shared implementation

Reuse `parent_language_management`, `parent_language_state`, public Parent
child selection, LANG01 and the shared worker in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py),
[parent_language.py](../../../tests/e2e/parent_language.py) and
[onpc_parent.pm](../../../tests/integration/graphical_smoke/lib/onpc_parent.pm).
Thread the explicit account/state through UiObservations and immutable comparisons.

## Implementation entry

Planned selector: `check_e2e_parent_language_isolation`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_parent_language_isolation`.
Retain check_e2e_parent_language and affected child-selection regressions; shared Parent launch changes retain case 6.
