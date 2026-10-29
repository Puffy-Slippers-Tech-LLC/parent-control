# 312 — Child reminder preferences persist across request surfaces

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
This is a planned complete case; its inventory ID and executable are unassigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **312a** — Installed overlay reminder editing, main Save/Cancel and empty-list readback.
- **312b** — Installed kiosk selected-child reminder binding and shared saved readback.
- **007** — Owned reboot and independent new-boot observation.

Estimate: 35–55 minutes.
Session exception: One continuous saved-reminder history spans both request surfaces,
one Cancel check and a real reboot to prove durable account isolation.

## Scope and acceptance

Customer goal: customize warnings for the correct child and retain those choices
when moving between the child overlay and kiosk. Use the
[child requirement](../../Specification.md) and
[preferences contract](../../SystemDesign/Frontends.md#child-reminder-preferences).

The installed reminder qualifications 312a and 312b passed on Ubuntu 26.04 and
Fedora 44 for their exact [catalogue scopes](../E2E-Building-Blocks.md#reminder-controls-and-notification-qualification).
Reuse their shared Application UI API operations; this complete case absorbs no independent
capability work. Host UI coverage does
not qualify an installed route. No E2E implementation or execution is authorized
by this documentation addition; the current next-task pointer stays unchanged.

The current facade binds overlay reminder operations to Riley, and its deletion
helper has no kiosk binding. Jordan's post-reboot overlay readback and kiosk
draft deletion therefore still need bounded prerequisite qualification before
this complete case is implemented. Delivered 312a/312b scope does not establish
those bindings; add their explicit prerequisite slice before this consumer.

## One saved-reminder journey

Apply the [cross-plan reuse map](../E2E-Building-Blocks.md#cross-plan-baseline-reuse):
C04r renews the existing kiosk caller only. Consume its applicable renewed
evidence and the same shared reminder operations without another feature
implementation; retain this case's missing bindings and complete reboot history.

Finite history: begin with both children's four untouched backend defaults and
record Jordan's reminder list and language. In Riley's overlay, create a
75-second reminder with literal text `Save <work>!`, edit its text to
`Save <work> & games!` and its trigger to 90 seconds, then save the main
preferences. Reopen Riley's preferences through the kiosk and require the same
saved list, including the exact edited text and trigger.

Keep one Cancel check: delete the custom row in the preferences draft, cancel
the main preferences, then reopen and require the saved list to be unchanged.
Delete all Riley's reminders, including the custom row, and save the empty list.
Reboot normally and re-enter both request surfaces; Riley's list must remain
empty on both, and Jordan's reminders and language must remain unchanged on
both. Reminder edits must preserve request choices, grant no time and change no
policy. Use public actions and independently observed results; private files,
broker calls as UI input and injected reminders supply no acceptance.

## Existing local coverage

Reuse the [local reminder editing allocation](../UI-and-E2E-Coverage.md#duplicate-review-and-allocation)
and executable owners in
[test_language_settings.py](../../../tests/ui/test_language_settings.py):
`test_child_preferences_reminders_sort_edit_save_cancel_and_empty_list` and
`test_reminder_creation_validation_and_candidate_translation` cover sorting,
duplicate-time refusal, exact literal text, translated descriptions and local
Save/Cancel behavior on both request surfaces. Do not import their widget matrix
or unchanged reruns into this case's steps, prerequisites or acceptance. These
tests supply no installed route, two-child transition or reboot result; the
complete customer history and missing bindings above remain required.

This journey covers saved preference persistence and Cancel. Native notification delivery,
fullscreen urgency, natural countdown and upgrade persistence remain in
[task 311](311-remaining-time-notifications.md). Geometry, scrollbar rendering and
popup appearance are excluded from automated acceptance under the UI mandate.

Assign one numeric case, finite recipe, shared worker and exact selector during
implementation, then regenerate coverage at close-out. This planned addition
registers no runnable case and claims no qualification or live acceptance.
