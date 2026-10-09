# 312b — Qualify selected-child kiosk reminder binding

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **312a** — Shared reminder editing, main Save/Cancel and empty-list readback.
- **300j** — Installed selected-child kiosk Preferences and approver independence.

Estimate: 20–30 minutes. First planned consumer:
[task 312](312-child-reminder-preferences.md); task 311 also uses this binding.

## Scope and acceptance

Qualify the same reminder operation on the station's selected-child binding.
Publicly save Riley's fixed 90-second `Save <work> & games!` row through the
shared overlay operation, then independently read that exact saved row in
Riley's kiosk Preferences. Save a station edit to 75 seconds and independently
require that value through Riley's overlay. Record Jordan's list/language and
require them unchanged after selecting Jordan then returning to Riley. Changing
approver Jamie → Casey → Jamie must retain Riley's list and language. Keep
request choices and public time/policy unchanged apart from elapsed time.
Qualify a second independent station entry and wrong-child/owner/surface,
ambiguous stored-ID and stale selected-child revision refusals. Do not repeat
312a's editor matrix or task 312's reboot history.

## Shared implementation

Use the [reminder qualification catalogue](../E2E-Building-Blocks.md#reminder-controls-and-notification-qualification)
for current slice readiness and reusable bindings.

Reuse 312a's public reminder helpers in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py), scoped separately to the
kiosk endpoint's `language-dialog` and `reminder-editor-dialog`. Use
`preferences-tabs`, `reminder-list`, stored-ID edit controls, editor fields and
main Save; each operation binds the current selected child's public identity.
The normal `RequestWindow._notifications_call` selected-child/revision route in
[main.py](../../../kiosk/oh_no_parent_control_kiosk/main.py) and shared
`PreferencesDialog` handlers own load/save. Preserve kiosk external-action
restrictions and refusal after account switches; no backend reads or writes
substitute for public readback.

Planned fixed selector: `check_e2e_kiosk_reminder_binding`; unregistered and
unqualified. Register before invoking
`tools/run-tests integration check_e2e_kiosk_reminder_binding`.
Retain affected selected-child language and overlay reminder qualifications.
