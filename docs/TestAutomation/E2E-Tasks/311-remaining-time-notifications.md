# 311 — Remaining-time system notifications

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
This is a planned complete case; its inventory ID and executable are unassigned.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **007** — Normal owned reboot and independent new-boot observation.
- **052** — Public child panel reads.
- **062** — Natural expiry and retained-session lock observation.
- **300i** — Child overlay personal-language Save and normal return.
- **312b** — Selected-child reminder binding, shared editing and independent saved readback.
- **311c** — Natural reminder observation and owned-banner fullscreen visibility/suppression.
- **135a** — Verified real no-action package upgrade and independent completion/notice.

Estimate: 40–60 minutes.
Session exception: The natural one-minute/15-second warning sequence, fullscreen branches, two child accounts and real reboot/upgrade persistence form a continuous customer history.

## Scope and acceptance

Customer goal: receive useful warnings before losing desktop access, including
while playing a fullscreen game, with independent durable reminder choices.
Use the [child requirement](../../Specification.md) and
[reminder implementation contract](../../SystemDesign/Screen-Time.md#remaining-time-notifications).
Backend storage, notification delivery, reminder-list editing and the fullscreen
preference GUI/public API are implemented; installed qualification remains pending.

Gate: complete the explicit installed reminder prerequisites before composing
this case. Tasks 312a/312b qualify the public editing and selected-child bindings;
311a qualifies the implemented fullscreen preference; 311b qualifies natural
body/urgency observations; 311c qualifies owned-banner visibility during the
existing task-129 fullscreen game. Reuse task 135a's verified no-action upgrade.
These remain independent capability slices, not work absorbed by this case.
Private preference file edits, broker calls as UI input, injected notification
events and accelerated private clocks cannot establish customer acceptance.

Bind notification reads to the ChildUI endpoint's `child-time-notification`
surface: `child-time-notification-message` supplies literal body and canonical
threshold seconds; `child-time-notification-urgency` supplies `critical`/`high`.
These IDs describe the emitted notification, not native banner visibility.
Qualify the repository-owned banner through the shared Application UI API;
require logical body text, current owned identity and independent visible/hidden
surface observations. Urgency alone proves no visibility. Preserve 311b's
canonical-seconds contract gate; no generic Shell adapter, coordinates, private
actors or pixel/rendering acceptance is required.

Finite history: start with untouched defaults and read all four saved thresholds
(10m, 5m, 1m and 15s) through the public reminder-management dialog. Begin the
delivery sequence with positive combined usable time above one minute but below
five minutes. Independently observe the 1m and 15s warnings once through natural
countdown; expect shared localized text and Critical urgency. Do not wait for
the 10m and 5m warnings to appear; their saved defaults remain checked, but their
delivery is outside this case's acceptance.
Use German for one child and English for the other. Through the public
dialog, create the final 15-second reminder with `Save your game now`, delete
the other reminders, and save. Task 312 owns the create/edit persistence history.
Verify literal custom text across the language switch and the other child's
unchanged reminders. Omit the extra
whitespace-only text delivery cycle.

Compare fullscreen-enabled Critical delivery with fullscreen-disabled High
delivery using the same owned fullscreen fixture and naturally reached threshold;
verify banner appearance/inhibition through the qualified public surface, independently
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
