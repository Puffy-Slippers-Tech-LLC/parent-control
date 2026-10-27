# Bedtime and weekly schedules — proposed backend design

[System design overview](../System-Design.md)

Status: proposal, not implemented. This document defines backend behavior and
integration work; it does not change the current [specification](../Specification.md).
The current enforcement contract remains in [Screen time](Screen-Time.md).
No installed acceptance is claimed by this design.

## Scope and policy

Add an optional weekly bedtime schedule for each managed child. Each calendar
day has one allowed-use window, expressed in the computer's local civil time.
For example, Monday's 07:00–21:00 window permits ordinary use on Monday from
07:00 inclusive until 21:00 exclusive. Outside that window, unused daily
allowance cannot authorize access.

The backend stores seven independent day entries. Applying the same schedule
to every day, or one schedule to Monday–Friday and another to Saturday–Sunday,
is simply an update of those entries. There is no separate workday/weekend
policy mode or competing source of schedule truth. Frontends can provide those
editing conveniences without changing the backend representation.

Retain the existing screen-time master switch. When it is off, neither daily
allowance nor bedtime is enforced and saved choices remain available. When it
is on, the daily allowance retains its existing meaning, including zero as
grant-only mode. Bedtime adds a restriction; enabling it does not create a
daily allowance or change measured usage. App restrictions remain independent.

One-time grants override both daily allowance and bedtime until their existing
elapsed-time expiry. This includes grants approved before bedtime and grants
approved while bedtime is in effect. Revocation removes that exception and
exposes the current schedule and daily allowance again. A weekday transition
must never clear, renew or extend a grant.

## Native backend mapping

Malcontent stores one repeating daily window, not a weekly schedule. Our broker
selects today's entry and materializes it through the public AccountsService
`com.endlessm.ParentalControls.SessionLimits` interface:

| Property | Desired value while screen-time control is on |
| --- | --- |
| `DailySchedule` | Today's allowed start/end in seconds since midnight |
| `DailyLimit` | Existing configured allowance in seconds |
| `LimitType` | `2` for daily allowance alone; `3` for allowance plus bedtime |
| `ActiveExtension` | Existing one-time grant, unchanged by schedule rotation |

Without a grant, usable time is constrained by both the allowance and the
schedule. An active grant permits access outside the normal window. Follow the
native semantics rather than introducing a separate grant type or secretly
clipping grants at bedtime.

Native windows require `0 <= start < end <= 86400`. The full-day window is
`(0, 86400)`. The first version supports one such window per day; a window
crossing midnight, multiple windows and an entirely blocked day are outside
this representation and must be rejected rather than approximated. An ordinary
overnight bedtime such as 21:00–07:00 is represented by allowed use 07:00–21:00.

Reference baseline: malcontent 0.14.0's
[property contract](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/accounts-service/com.endlessm.ParentalControls.SessionLimits.xml),
[limit calculation](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent/session-limits.c)
and [timer estimate interface](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml).
Supported distro builds still require qualification, especially around midnight
and daylight-saving transitions.

## Durable state and backend API

Extend the existing root-owned per-child [preference record](State.md) with a
policy section, conceptually:

```json
{
  "bedtime": {
    "enabled": true,
    "days": {
      "monday": [25200, 75600],
      "tuesday": [25200, 75600],
      "wednesday": [25200, 75600],
      "thursday": [25200, 75600],
      "friday": [25200, 82800],
      "saturday": [28800, 82800],
      "sunday": [28800, 75600]
    }
  }
}
```

Use stable weekday names and integer seconds, with minute-aligned bounds in
the initial API. Require exactly seven known days and validate every entry,
even when disabled. Missing legacy bedtime settings normalize to disabled with
full-day windows, preserving existing behavior. New child defaults are the same.

Use the existing migration framework for a new preference schema version:
this adds enforcement policy that an older broker must not silently ignore or
discard. Append a migration from the current version at implementation time;
do not modify released migrations. Migration changes records only; native
policy reconciliation follows separately under the [migration contract](Data-Migration.md).

Add an administrator-only system D-Bus operation to save the complete
screen-time policy: master enablement, daily allowance and weekly bedtime
settings. Validate caller, current child eligibility and the whole payload
before effects. Preserve existing method signatures; route their writes through
the same implementation while retaining any saved bedtime settings. Generic
preference writes must not provide a way to bypass policy validation or activation.

Expose read-only schedule and effective-status data to already-authorized
Parent, child-self and kiosk callers. Child and kiosk request-choice APIs must
not be able to modify bedtime. Policy reads and writes use the existing broker
identity and transaction boundaries described in [Broker](Broker.md).

## Daily reconciliation and service lifetime

The broker owns one scheduler across managed children. It must be running while
weekly bedtime policy requires rotation; a frontend being open is not a
prerequisite. Reconcile the applicable schedule:

- Before publishing normal policy readiness at broker startup.
- At each local calendar midnight.
- On resume and after system-clock or timezone changes.
- Immediately after a successful parent policy change.
- Before admitting a managed login or unlock if schedule freshness is uncertain.

Always select from the current local date and timezone, rather than incrementing
a remembered weekday. Recalculate the next local midnight after each event;
never assume a day lasts 86400 elapsed seconds. Catch up directly to today's
policy after downtime, suspension or missed callbacks. Coalesce duplicate events
and perform idempotent writes only where native state differs.

Use public system clock/timezone and sleep lifecycle notifications, with a
bounded periodic freshness check as recovery for missed events. Serialize
reconciliation with policy edits, approvals and revocation through the existing
shared transaction lock. Contention queues another attempt; it must not drop a
day transition. Re-read current preferences when the lock is acquired.

An in-memory freshness key can include the local date, timezone identity and
policy revision, but is only an optimization. Read back the native state before
acknowledging reconciliation; after a crash or backend owner replacement, an old
success marker is not proof of the current policy.

## Admission and running-session enforcement

Retain malcontent as the authority deciding access under the installed daily
window. Native PAM checks cover fresh login. Our existing GDM authentication
helper covers password unlock, which does not repeat PAM account management.
GNOME's native deadline and the child extension's countdown cover an already
running desktop. See [countdown and PAM enforcement](Screen-Time.md#countdown-and-expiry-enforcement).

Those paths currently consult the installed native window, not a weekly policy.
A midnight timer alone is insufficient: yesterday's native window remains valid
to malcontent until replaced. The implementation must establish a freshness
handoff at startup, resume and login/unlock so the native check cannot admit a
child using yesterday's window. This coordination is required new work, not an
existing guarantee of the current asynchronous session-preparation call.

Use a bounded broker reconciliation/readiness operation before the existing
native admission decision; the PAM helper must not independently interpret the
seven-day schedule. If freshness cannot be established, deny managed admission
with an availability error, preserving administrator recovery and kiosk access.
For retained sessions, complete reconciliation before permitting usable desktop
access after resume; a notification delivered after access resumes does not
establish this ordering. Review the supported GNOME/logind lifecycle before
claiming that barrier is implemented. If public APIs cannot establish it, retain
the limitation explicitly and resolve it before claiming gap-free enforcement.

This avoids a second weekly-policy engine while making the scheduler's ownership
and failure behavior explicit. A reconciliation failure must be reported and
retried; it must never install a full-day fallback. A stale permissive window on
an active desktop requires the existing public lock path until freshness is
restored. AccountsService alone cannot detect broker failure or stale dates;
broker recovery and this session-side freshness handling require dedicated checks.

## Transactions and existing grants

Reuse the broker's verified snapshots and rollback for native limit flags,
schedule, daily allowance, grant and durable preferences. Publish success only
after the desired native state and saved policy are verified. Reconciliation
failure preserves durable intent for retry and reports failed activation.

The existing time-state helper temporarily installs a full-day schedule. Do not
blindly reuse that bridge for weekday rotation: it can temporarily relax a real
bedtime. Define and verify write ordering for schedule changes and flag changes,
including crash points and observer-visible intermediate states. The properties
are separate writes, not an atomic AccountsService transaction. Ordinary rotation
with unchanged flags should update only the schedule and preserve the grant.

Keep existing master-toggle grant-clearing behavior. Edits while control stays
on preserve grant deadlines. Policy changes revalidate in-flight approvals under
the existing request revision/snapshot contract. Request cancellation and app
termination retain their existing transaction semantics.

## Effective time and approval calculations

Extend backend status to distinguish raw daily allowance remaining, grant
remaining, current usable time, today's closing boundary and the next allowed
opening. Include whether bedtime is the current restriction. Keep existing D-Bus
status signatures for compatibility and add a richer status operation.

Parent status, request estimates, child countdown and lock decisions must agree.
Preserve the current treatment of ongoing active usage: a fresh recorded-use
query must not move a running countdown deadline forward. Calculate local civil
boundaries using timezone-aware calendar operations, not elapsed seconds added
to midnight. Use malcontent's estimates and supported limit calculation where
appropriate; qualify any disagreement with those native results rather than
displaying an access promise the backend will deny.

Proposed request behavior: fixed requests add their duration to the greater of
the schedule-constrained daily balance and current grant balance. For example,
at 20:50 with bedtime at 21:00, 90 unused daily minutes and no grant, requesting
30 minutes creates 40 minutes of elapsed access, ending at 21:30. This is a
deliberate extension of the current allowance-based arithmetic and requires
specification approval before implementation. Rest-of-day retains its current
local-midnight expiry and overrides bedtime until that expiry.

## Validation and implementation boundaries

Backend implementation must update the owning specification, state, broker,
screen-time and lifecycle contracts alongside executable changes. Scheduling
does not alter application-policy ownership or create a new privileged service
unless lifecycle analysis demonstrates one is necessary. Extend approved,
bounded diagnostics with reconciliation reason, freshness and outcome categories;
do not log child identities or their schedule contents.

Use focused engineering checks for seven-day validation, defaults/migration,
authorization, day selection, clock/timezone changes, missed events, retries,
write ordering, rollback and races with approval/revocation. Exercise grants
across bedtime, midnight and daylight-saving transitions against the actual
supported malcontent versions; source inspection alone does not establish those
edge cases work.

Installed acceptance must observe bedtime locking despite unused allowance,
fresh-login denial, retained-session unlock denial, morning reopening and
authenticated grant/revocation behavior. Cover distinct weekday/weekend windows,
startup/resume catch-up, backend failure/recovery and isolation between children.
Engineering clock injection belongs in engineering tests; customer acceptance
uses the public actions and natural boundaries required by the
[test documentation](../TestAutomation/README.md). This document creates no
completed task or passing acceptance claim.
