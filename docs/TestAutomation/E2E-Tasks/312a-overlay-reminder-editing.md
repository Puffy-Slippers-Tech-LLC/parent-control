# 312a — Qualify saved overlay reminder editing

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **300i** — Installed Riley overlay Preferences and language ownership.

Estimate: 20–30 minutes. First planned consumer:
[task 312](312-child-reminder-preferences.md); shared editing also serves task 311.

## Scope and acceptance

Qualify the fixed Riley overlay reminder draft/save operation. Read the four
untouched defaults, create a 75-second row with literal `Save <work>!`, edit it
to 90 seconds and `Save <work> & games!`, and save the main Preferences.
Independently reopen and require the exact saved record with its stable ID.
Delete that row in a draft, Cancel main Preferences and independently require
the saved record unchanged. Delete all rows, Save and independently require the
empty saved list. Capture unchanged language, request choices and public
time/policy, allowing only declared elapsed time; editing grants no access.
Use a second independently entered Preferences session to qualify binding and
refuse wrong-child/surface, missing or ambiguous IDs, busy/modal-blocked input
and stale editor targets. Local duplicate/sorting/translation matrices remain
with [UI allocation](../UI-and-E2E-Coverage.md#duplicate-review-and-allocation).

## Shared implementation

Use the [reminder qualification catalogue](../E2E-Building-Blocks.md#reminder-controls-and-notification-qualification)
for current slice readiness and reusable bindings.

Extend the shared Application UI API facade in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py) and installed observation
registration in [ui_observations.py](../../../tests/e2e/ui_observations.py).
Bind the child-overlay endpoint's `language-dialog` and owned
`reminder-editor-dialog`; use `preferences-tabs=reminders`, `reminder-list`,
`reminder-add`, stored-ID edit/delete controls, `reminder-text`, `reminder-value`,
`reminder-unit=second`, editor Save and main `language-continue|cancel`.
Reuse `PreferencesDialog._commit_reminder`, `_delete_reminder`, `_submit` and
`_dismiss`, and `ReminderDialog._submit` in
[preference_dialog.py](../../../kiosk/oh_no_parent_control_kiosk/preference_dialog.py),
through their public handlers. Saved readback re-enters the ordinary load path;
no private preference/broker input or preview notification supplies acceptance.

Planned fixed selector: `check_e2e_overlay_reminder_editing`; unregistered and
unqualified. Register before invoking
`tools/run-tests integration check_e2e_overlay_reminder_editing`.
Retain affected overlay-language and request-preservation qualifications.
