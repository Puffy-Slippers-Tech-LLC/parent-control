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
Session exception: One uninterrupted two-child history spans both request surfaces,
saved changes, cancellations and a real reboot to prove durable account isolation.

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

Finite history: begin with the backend's four untouched default reminders. In
Riley's overlay, create a 75-second reminder with literal text `Save <work>!`,
edit its trigger to 90 seconds, and save the main preferences. Read rows in
ascending remaining seconds; custom text must stay literal and its smaller
trigger description must reflect 90 seconds independently of the text. No
illustrative `Custom reminder` preset may appear.

Attempt a second reminder at an existing threshold, including 1 minute versus
60 seconds. Require the editor footer's duplicate warning, unavailable Save and
unchanged saved data; correct the trigger and cancel the editor. Delete a saved
row and cancel the main preferences; reopening must retain the saved list.
Change Riley's language to German and require translated default text/trigger
descriptions while the literal custom text and request choices remain intact.

Reopen Riley's preferences through the kiosk and require the same saved list.
Jordan must retain independent defaults and language. Save an empty list for
Riley, reboot normally, and re-enter both request surfaces; Riley's list must
remain empty and Jordan's list unchanged. Reminder edits must not grant time or
change policy. Use public actions and independently observed results; private
files, broker calls as UI input and injected reminders supply no acceptance.

This task covers preference persistence and refusal. Native notification delivery,
fullscreen urgency, natural countdown and upgrade persistence remain in
[task 311](311-remaining-time-notifications.md). Geometry, scrollbar rendering and
popup appearance are excluded from automated acceptance under the UI mandate.

Assign one numeric case, finite recipe, shared worker and exact selector during
implementation, then regenerate coverage at close-out. This planned addition
registers no runnable case and claims no qualification or live acceptance.
