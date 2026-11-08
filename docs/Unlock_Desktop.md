# Unlocking a desktop without time: open question

When a child has no usable time, can sign-in or return to a locked desktop ever
expose an interval in which ordinary desktop input works before denial or
renewed locking? Should the product promise that such an interval never exists,
or retain the specification's current denial-or-relock behavior?

By user decision, the former task **171**, engineering obligation **142**, and
its additional exposure tests are removed from execution scheduling in Plans
A, B and C. This is an open question for further investigation, not an execution
plan or a queued task. Removal supplies no passing result or completed
qualification and creates no blocker for the current queue. Existing ordinary
login, unlock, natural-expiry, PAM-denial and recovery coverage remains unchanged.

## Current behavior and the stricter question

The [screen-time specification](Specification.md#screen-time-setup-and-enforcement)
distinguishes these outcomes:

- **TIME-008:** the active child desktop locks at zero usable time; unlocking
  without new time is denied or followed by renewed locking. Fresh login without
  time is denied, and confirmed exhaustion is explained as a time restriction.
- **TIME-009:** natural exhaustion retains the child's session and apps, while
  another user's foreground session continues. An expired grant alone does not
  require locking when daily time remains.
- **TIME-010:** legitimate positive time permits return to retained work or a
  fresh login without restarting the grant's original duration.

The former additional question was stricter: **no transient unmanaged usable
desktop before safe denial or relock**. That asks about the entire entry
interval, including whether any ordinary input reaches an app, rather than
only the eventual locked or denied state. It is not established by the
specification's denial-or-relock wording. This document chooses no new atomic
input barrier, permitted grace interval or lock deadline, and claims no product
fix or newly observed failure.

The [current screen-time design](SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement)
uses PAM checks for fresh login and retained-session authentication. The child
extension requests the public GNOME ScreenSaver lock after confirmed exhaustion
and reevaluates enforcement after unlocking without new time. Initial failed
time reads are errors, not confirmed zero balances. Startup and unlock also
invoke asynchronous broker-owned
[app-policy reconciliation](SystemDesign/Applications.md#session-entry-reconciliation).
That reconciliation is not a compositor admission barrier. Its presence does
not establish atomic prevention of desktop input; its asynchronous nature alone
also does not prove that a particular login or unlock exposes usable input.

## Concrete situations to understand

Jordan is the child whose time has run out. Riley is an unrelated user with a
retained foreground activity. “Usable desktop” means ordinary input can reach
Jordan's desktop or original app; a rendered frame, a lock request, an unlocked
hint or a successful authentication response alone does not answer that question.

| Situation | Existing product expectation | Additional open question |
| --- | --- | --- |
| **Fresh login at zero** | Screen-time control is on, daily and grant balances are zero, and Jordan supplies the correct normal password at sign-in. Entry is denied for time restriction. | Is there any interval between authentication and final denial in which Jordan receives a usable desktop? What observation distinguishes genuine pre-entry refusal from a desktop that starts and then relocks? |
| **Return to an expired locked desktop** | Jordan has original work in a retained locked session, no daily time and an expired grant. Correct-password return without new time is denied or followed by renewed locking. | Does any ordinary input reach the retained desktop before that denial or relock? Is an apparently exposed desktop actually interactive, and where does the interval begin and end? |
| **Ordinary foreground expiry** | Jordan begins with real positive time and usable original work. All usable time expires naturally. The desktop locks while the same session and apps remain, and Riley's foreground activity continues when Riley is active. | How does the observable transition from usable to protected input relate to the original deadline? Would a claim of no transient usable input add a stronger guarantee than the ordinary timed-lock behavior already covered? |

The original exposure-observation concept concerned the full transition:
authentication or entry, any intermediate usable state, and final safe denial
or lock. A final lock snapshot cannot reveal what happened earlier. Observing a
transient frame is also different from observing ordinary app input taking
effect. The exact meaning and observability of the stricter promise remain part
of this question.

## Recovery, retained work and other users

A legitimate parent grant or remaining daily allowance changes the situation:
Jordan should be able to enter or unlock with normal credentials and continue
the same retained session and unaffected original work. The original grant
deadline continues through lock and return. Positive time must not be mistaken
for a stale exhausted state or be rejected merely to avoid the exposure question.

Natural expiry itself does not close apps or log Jordan out. App-policy actions
and expired-grant reconciliation have their own documented running-app effects;
those effects must not be confused with loss of the original session. Riley's
original session, work, usable input, policy and time remain independent of
Jordan's restriction and recovery.

These are constraints on the family situations under discussion, not a request
to repeat existing login, expiry or recovery journeys. No logout, loss of work,
denial of legitimate positive time or interruption of another user is selected
as a solution to the stricter question.

## What existing observations do not establish

The existing [graphical expiry owner](../tests/integration/system_graphical_expiry.py)
contains a one-second login history, retained natural lock, legitimate time
recovery and other-user continuity observations. Its
[zero-time PAM checks](../tests/integration/system_session_expiry.py) observe
denied authentication/account checks and successful positive-time admission.
The [child indicator](../child/remainingTimeIndicator.js) also distinguishes
confirmed loaded exhaustion from unavailable time information before requesting
a lock.

Those source paths and their ordinary results remain useful. A PAM result,
retained-session result or final protected-input observation does not establish
the absence of an earlier usable interval. Conversely, lack of that interval
observation is not itself evidence of exposure. No live investigation or new
qualification is claimed here.

The unresolved issue is the intended guarantee and how it relates to supported
GNOME login, unlock and input protection. Further investigation may clarify the
actual interval and the distinction between the current specification and an
atomic no-input promise. This document schedules no implementation and changes
neither expectation.
