# 311 — Remaining-time system notifications

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
This is a planned complete case; its inventory ID and executable are unassigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **007** — Normal owned reboot and independent new-boot observation.
- **052** — Public child panel reads.
- **062** — Natural expiry and retained-session lock observation.
- **300i** — Child overlay personal-language Save and normal return.

Estimate: 40–60 minutes.
Session exception: The natural one-minute/15-second warning sequence, fullscreen branches, two child accounts and real reboot/upgrade persistence form a continuous customer history.

## Scope and acceptance

Customer goal: receive useful warnings before losing desktop access, including
while playing a fullscreen game, with independent durable reminder choices.
Use the [child requirement](../../Specification.md) and
[reminder implementation contract](../../SystemDesign/Screen-Time.md#remaining-time-notifications).
Backend storage, notification delivery and reminder-list dialog code are
implemented; installed qualification remains pending.

Gate: the fullscreen notification preference GUI control and its public
Application UI API binding remain unimplemented. The existing reminder-management
dialog preserves that backend field without exposing a control; implement and
qualify its normal preference handler before the fullscreen branches. The child
reminder-management dialog and its public controls also need installed
qualification. Qualify their normal Save/CRUD handlers, and shared GNOME
notification/provider and owned fullscreen-fixture operations, before implementing
this case. Extract independent capability slices under the
shared sizing contract as needed; this planned case does not absorb them.
Private preference file edits, broker calls as UI input, injected notification
events and accelerated private clocks cannot establish customer acceptance.

Bind notification reads to the ChildUI endpoint's `child-time-notification`
surface: `child-time-notification-message` supplies literal body and canonical
threshold seconds; `child-time-notification-urgency` supplies `critical`/`high`.
These IDs describe the emitted notification, not native banner visibility.
Qualify Shell banner accessibility through the scoped external-provider adapter;
require logical body/accessibility text equality and owned banner identity,
without coordinates, private actors or pixel/rendering acceptance.

Finite history: start with untouched defaults and read all four saved thresholds
(10m, 5m, 1m and 15s) through the public reminder-management dialog. Begin the
delivery sequence with positive combined usable time above one minute but below
five minutes. Independently observe the 1m and 15s warnings once through natural
countdown; expect shared localized text and Critical urgency. Do not wait for
the 10m and 5m warnings to appear; their saved defaults remain checked, but their
delivery is outside this case's acceptance.
Use German for one child and English for the other. Through the public
dialog, create a 75-second reminder with `Save your game now`, update it to 15
seconds, delete the other reminders, and save. Verify literal custom text across
the language switch and the other child's unchanged reminders. Omit the extra
whitespace-only text delivery cycle.

Compare fullscreen-enabled Critical delivery with fullscreen-disabled High
delivery using the same owned fullscreen fixture and naturally reached threshold;
verify banner appearance/inhibition through the qualified provider, independently
of the urgency read. A grant renewal must rearm a crossed reminder without a
duplicate during an unchanged countdown. Observe natural lockout with no stale
product warning on the lock screen.

Save an empty list for one child and a customized list/fullscreen choice for the
other. Re-enter after a real reboot and a normal verified package upgrade;
require retained choices, no restored presets for the empty list, and delivery
of the customized reminder during renewed access. Keep all limits/grants and
the other child's state independent of reminder changes.

Register a numeric case, finite recipe, shared worker and exact selector during
implementation, then use `tools/generate_test_coverage.sh`. No runnable selector,
scenario registration, provider qualification or live acceptance is supplied by
this documentation addition.
