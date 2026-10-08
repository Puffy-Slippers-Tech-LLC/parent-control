# 312 — Child reminder preferences persist across request surfaces

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
This is a planned complete case; its inventory ID and executable are unassigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **300i** — Installed child-overlay preferences and language selection.
- **300j** — Installed kiosk selected-child preferences and language selection.
- **007** — Owned reboot and independent new-boot observation.

Estimate: 35–55 minutes.
Session exception: One continuous saved-reminder history spans both request surfaces,
one Cancel check and a real reboot to prove durable account isolation.

## Scope and acceptance

Customer goal: customize warnings for the correct child and retain those choices
when moving between the child overlay and kiosk. Use the
[child requirement](../../Specification.md) and
[preferences contract](../../SystemDesign/Frontends.md#child-reminder-preferences).

Gate: qualify the installed reminder list/editor public controls through the
shared Application UI API facade before composing this case. Extract independent
capability work if required by the shared sizing contract. Host UI coverage does
not qualify an installed route. No E2E implementation or execution is authorized
by this documentation addition; the current next-task pointer stays unchanged.

## One saved-reminder journey

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

## Smaller editing checks

Duplicate-time refusal, ascending trigger sorting and detailed translated
descriptions belong to the [local reminder editing allocation](../UI-and-E2E-Coverage.md#duplicate-review-and-allocation)
in `tests/ui/test_language_settings.py`. Preserve these functional assertions:

- Equal thresholds, including 1 minute versus 60 seconds, show the duplicate
  warning, disable editor Save and leave saved data unchanged; a distinct
  threshold clears the refusal.
- Rows sort by ascending remaining seconds after editing. Literal custom text
  stays exact, its separate trigger description reflects the edited duration,
  and no illustrative `Custom reminder` preset appears.
- German candidate-language checks translate default text and trigger
  descriptions while retaining literal custom text and request choices.

Existing local tests cover parts of this matrix; remaining assertions stay
pending with that owner. These checks need no additional two-child history or
restart and do not qualify the installed route or claim live acceptance.

This journey covers saved preference persistence and Cancel. Native notification delivery,
fullscreen urgency, natural countdown and upgrade persistence remain in
[task 311](311-remaining-time-notifications.md). Geometry, scrollbar rendering and
popup appearance are excluded from automated acceptance under the UI mandate.

Assign one numeric case, finite recipe, shared worker and exact selector during
implementation, then regenerate coverage at close-out. This planned addition
registers no runnable case and claims no qualification or live acceptance.
