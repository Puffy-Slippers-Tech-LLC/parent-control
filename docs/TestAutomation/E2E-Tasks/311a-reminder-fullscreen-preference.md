# 311a — Qualify saved reminder fullscreen preference

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **312a** — Installed overlay reminder load/edit/main Save and Cancel.

Estimate: 20–30 minutes. First planned consumer:
[task 311b](311b-natural-reminder-observation.md); final customer case:
[task 311](311-remaining-time-notifications.md).

## Scope and acceptance

Qualify Riley's account-wide fullscreen boolean through overlay Preferences.
With a nonempty loaded reminder list and the default true value, save false and
independently reopen to require false. Set a true draft, Cancel and independently
require the saved false value unchanged. This proves a saved nondefault and a
discarded change with one Save instead of two. Compare exact reminder records,
language, request choices and public time/policy before/after, with elapsed-time
bounds. The necessary saved-value reopen supplies independent entry. Cover
wrong-child/surface, stale, ambiguous, loading, busy and empty-list disabled
control refusals in focused harness checks before discovery/input; preserve
those shared runtime guards without repeating the editor's qualification matrix.
Notification delivery and fullscreen suppression are separate qualifications;
a saved boolean supplies no delivery acceptance. Task 311c still explicitly
saves both enabled and disabled choices before checking their distinct banner
effects. Local boolean/editing combinations remain in
`tests/ui/test_language_settings.py::test_child_preferences_reminders_sort_edit_save_cancel_and_empty_list`.

## Shared implementation

Use the [reminder qualification catalogue](../E2E-Building-Blocks.md#reminder-controls-and-notification-qualification)
for current slice readiness and reusable bindings.

Use shared public Preferences/reminder helpers and `reminder-show-in-fullscreen`
`getValue|setValue` with canonical booleans, followed by main Save/Cancel and a
fresh ordinary load. The control and handlers are implemented:
`PreferencesDialog._build_reminders_page`, `_fullscreen_changed`, `_submit` and
`_notifications_saved` in
[preference_dialog.py](../../../kiosk/oh_no_parent_control_kiosk/preference_dialog.py).
The shared GTK adapter's `_generic` boolean setter in
[application_ui.py](../../../common/oh_no_parent_control_ui/application_ui.py)
runs the switch's normal handler. Extend installed facade/worker bindings rather
than adding a new product preference or private storage route.

Planned fixed selector: `check_e2e_reminder_fullscreen_preference`; unregistered
and unqualified. Register before invoking
`tools/run-tests integration check_e2e_reminder_fullscreen_preference`.
Reuse unchanged reminder Save/Cancel and overlay-language qualification; rerun
only the affected branches if shared operations change.
