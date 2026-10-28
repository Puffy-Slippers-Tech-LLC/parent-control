# Bedtime and weekly schedules — proposed design

[System design overview](../System-Design.md)

Status: proposed, not implemented. This does not change the current
[specification](../Specification.md) or claim installed acceptance.
Use existing Malcontent APIs and behavior. Add one weekly preference, one
broker evaluator and integrations in the existing PAM helper and child component.
No native weekly API, daily window rotation, extra daemon or grant rewriting.

## Policy

Each child has seven independent allowed-use windows in the machine's local
timezone. Monday 07:00–21:00 allows ordinary use from 07:00 inclusive to 21:00
exclusive. Applying one value to all days or to workdays/weekends is an editing
convenience, not another policy mode.

The existing master switch controls daily allowance and bedtime together.
Turning it off retains choices and clears grants as today. Zero daily allowance
remains grant-only mode. App policy stays independent.

An active one-time grant overrides allowance and bedtime until its existing
elapsed-time expiry. Revocation exposes the current allowance and window.
Date changes never reset usage or clear, renew, rebase or extend grants.

Bounds are minute-aligned integer seconds, `0 <= start < end <= 86400`.
`(0, 86400)` permits the full day, subject to daily allowance. One window per
day is supported; multiple windows, crossing-midnight windows and entirely
blocked days are rejected. Overnight bedtime 21:00–07:00 means allowed use
07:00–21:00.

Window membership follows the actual local clock. Skipped clock labels never
occur; repeated labels obey the same window on both occurrences. Grant expiry
continues using native elapsed-time semantics.

## Existing backend and one evaluator

Keep live Malcontent time control in its existing daily-allowance mode,
`LimitType=2`; disabled remains `0`. Keep its daily limit, usage recording,
grant and existing transaction bridge. Do not persist weekday windows in
`DailySchedule` or change flags at bedtime, midnight or grant expiry.

The broker selects today's saved window. It uses the existing public
`Malcontent.SessionLimitsBuilder` to build an **in-memory** schedule-only
limit with no allowance or extension. Its `check_time_remaining(now, 0)`
supplies membership. Nothing from this object is written to AccountsService.
Read the real grant through native `get_active_extension(now)`, separately:

```text
pass if saved master control is off or native limits are disabled
pass if bedtime is disabled
pass if the native one-time grant is currently active
otherwise pass only inside today's allowed window
```

Passing does not supply daily time; native daily enforcement still applies.
PAM and the child consume this same broker result, never duplicate weekday
rules. The fast read obtains preferences and native limits, never usage history,
authentication or policy writes. Missing/malformed data is unavailable, not off.

The native schedule remainder counts civil seconds. Use its membership boolean,
but calculate elapsed boundaries in one timezone-aware broker helper. Enumerate
valid civil endpoints and midnights over eight local dates, considering both
occurrences of ambiguous endpoints and skipping nonexistent ones. Include actual
timezone transitions, found by bracketing/bisecting public
[timezone interval lookups](https://docs.gtk.org/glib/method.TimeZone.find_interval.html).
Select the next membership change. Merge contiguous allowed days; seven full-day
entries have no bedtime closing. Reload machine timezone rules after changes,
rather than retaining a startup offset or adding 86400 elapsed seconds.

## Storage and broker API

Extend the existing root-owned [preference record](State.md):

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

Require exactly seven known days and validate disabled settings too. Reject
booleans as integers, unknown/duplicate JSON keys and partial weeks. Use the
existing bounded transport. Legacy and new defaults are disabled/full-day.
Append a new preference-schema migration because older writers must not ignore
enforcement policy; keep released migrations unchanged. Follow
[Data migration](Data-Migration.md); no native weekly state is migrated.

Add a complete screen-time-policy save to the product broker, administrator-only.
Preserve existing signatures. `SetParentControl` retains saved bedtime;
`SetPreferences` preserves it and keeps its existing storage-only allowance
semantics. Child/kiosk request-choice writes cannot alter bedtime.

Fast bedtime reads and richer status are product broker additions, not new
Malcontent APIs. Child reads derive the target from bus credentials; privileged
PAM may select an eligible child. Parent/kiosk reads retain existing target-role
checks under [Broker](Broker.md). Rich usage status has its existing separate
query budget; it is never an admission dependency.

## Lifetime, concurrency and recovery

No root scheduler or boot dependency is needed. Every fast read evaluates the
current date. The child schedules absolute boundaries and refreshes on policy/
grant changes, midnight, resume, clock/timezone changes and broker-owner changes.
A five-second refresh recovers missed signals; a known closing uses its timer,
not polling.

Give the fast read one three-second end-to-end budget, including native reads
and at most one retry of a changed snapshot. Keep existing request serialization,
including Polkit lifetime, but do not acquire that long lock for bedtime reads.
Mark actual effects and revisions per child. Read only a stable snapshot;
an unanswered password prompt and another child's transaction cannot block it.

Admission refuses a busy snapshot. An already running desktop can retain its
last verified permission during mutation contention, until its original
absolute boundary; contention cannot extend it. Other read failures or owner
loss lock with an availability error, retaining balances for diagnostics.
Ignore stale owners/replies and check expiry again when a reply arrives.

Keep the D-Bus main loop free of blocking management work. Register the fast
read after configuration/native adapters are validated, before startup extension
reassertion can wait on Shell; complete remaining startup in a worker. Management
stays not-ready until normal checks pass. Migration/reboot guards remain in
force. The fast path never enters a user bus, invokes PAM or activates Shell,
so startup and unlock cannot wait indefinitely on each other.

Saved bedtime applies when both saved master control and live native limits
are enabled. Native `0` means inactive, preserving retained choices after
[removal/reinstallation](Lifecycle.md#broker-readiness). A parent reapply
reactivates them. An unexpected enabled type, including a crashed transition
bridge, is unavailable until verified reapply; stable product state is `2`.
There is no activation marker, grant reconstruction or recovery journal.

## Login, unlock and resume

Access requires native daily permission **and** the bedtime check. Extend the
product PAM helper to check bedtime before native fresh-login account checks,
again at session opening, and before GDM password unlock. Use current time,
not authentication-start time. Unavailable and confirmed exhausted remain
distinct. Preserve administrator, kiosk and verified administrative user-bus
transport exemptions from [existing enforcement](Screen-Time.md#countdown-and-expiry-enforcement).

The existing child component adds one guard, active in user/unlock-dialog modes:

- Install it before reporting component readiness. Evaluate on enable and startup
  completion; use a before-redraw check for pending expiry. Unknown permission
  stays restricted. Bedtime readiness requires an effective native lock and
  a lockable account; passwordless/lock-disabled configurations cannot pass.
- At a closing boundary, call public `ScreenShield.lock(false)` directly in
  Shell's main loop, without a D-Bus hop.
- On public `locked-changed` becoming false, perform the fast own-account read
  synchronously, within its three-second budget. Recheck absolute expiry.
  Denial, stale data or failure calls `lock(false)` in the same callback before
  yielding to painting/input. This covers authentication, logind Unlock and
  ScreenSaver deactivation despite GNOME's daily-only native guard.
- Use a reentrancy guard and one owned idle reassertion after a rejected unlock,
  preserving the actual lock and logind hint after native completion settles.
  The existing unlock-continuation controller consults cached permission before
  deactivation; completion performs the single fresh blocking read.
- Acquire the public logind sleep-delay inhibitor before sleep notifications.
  On prepare-for-sleep, invalidate permission, lock synchronously, verify the
  lock and release the inhibitor. Reacquire on resume. Respect logind's finite
  delay budget; failure to lock is a protection failure, never readiness success.
- Owner loss/failed refresh locks. Recovery or morning reopening never unlocks
  automatically. Release owned timers, signals and inhibitor on shutdown.

The bounded synchronous check is an explicit cost, once per completed unlock,
with no human wait or usage query. No Shell method replacement, private-state
write or new unlock-veto API is required. This uses normal desktop event-loop
timing, not a hard real-time promise against a frozen/compromised compositor.
Installed acceptance must prove startup and unlock protection before usable
desktop access; a later asynchronous relock or polling is not that proof.

## Saves, grants and failure ordering

A bedtime-only save atomically replaces the complete bedtime section. It writes
no native time state and changes no grant or app policy. Combined saves use the
existing verified native transaction and rollback:

1. Authorize/validate everything and capture old preference policy, native time/
   filter state and extension state before effects.
2. Mark this child's effects in progress. If new policy can deny current access,
   lock its live desktops through verified public Shell endpoints and await lock
   acknowledgement before writes. Also prelock an earlier boundary less than the
   five-second refresh plus three-second read budget away. Required-lock failure
   aborts; no live desktop needs no lock.
3. Apply native master/allowance/grant/filter changes through the existing
   transaction bridge. Preserve grants for an already-enabled edit and clear
   them on master-toggle transitions, as today. Bedtime-only saves skip this step.
   The separate child/PAM bedtime guard remains effective during the bridge.
4. Recheck current time and required locks immediately before atomically saving
   preferences; machine work may have crossed a boundary. Merge current personal/
   unrelated request choices, verify preferences and changed native values, then
   publish the stable revision, notify clients and report success.

On ordinary failure, keep admission gated while restoring/verifying old native
time/filter state, old preference policy and extension state, preserving unrelated
edits. Successful rollback reports the failed save. Failed rollback leaves that
child unavailable and reports recovery failure; parent reapply uses the same
verified path. Other children retain their own stable permission.

Native properties and preferences are not jointly crash-atomic. Restart reads
actual native master/allowance/grant plus the complete old-or-new bedtime record.
Native off stays off; enabled `2` applies saved bedtime; an interrupted bridge
is unavailable. Report configured/live allowance mismatches without replaying
limits or approvals. These rules define each crash outcome without another store.

Keep existing approval/revocation and irreversible app-termination rules.
Include bedtime in approval-policy snapshots. Before clearing a grant overriding
closed bedtime, lock as above. Recalculate request time after authentication.
Weekday changes write nothing and cannot be delayed by a password prompt.

## Status and request calculations

Preserve existing raw-balance signatures. Rich status distinguishes configured/
live enablement, raw daily balance, grant balance, usable time, restriction reason,
evaluation time, absolute closing/expiry and next opening. An opening is not a
promise of daily allowance.

Combine the native daily estimate with the same broker bedtime result:

```text
ordinary = inside_window ? min(native_estimate, time_to_closing) : 0
usable   = max(ordinary, native_grant_remaining)
```

A native estimate already including the grant does not add it twice. Preserve
the existing active-use deadline and recorded-use fallback; a fresh query must
not move a running deadline forward. Keep daily-reset behavior and grant expiry
distinct. Failed reads are unavailable, not invented free time or exhaustion.

Keep fixed requests at `max(raw_daily_remaining, grant_remaining) + requested`.
At 20:50, bedtime 21:00, 90 unused daily minutes and no grant, a 30-minute request
creates a 120-minute grant ending 22:50. Explain that unused allowance carries
past bedtime. Using a schedule-clipped request base would change the existing
contract and is excluded. Rest-of-day keeps its existing local-midnight expiry.

## API evidence and implementation acceptance

Existing Malcontent references:
[property contract](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/accounts-service/com.endlessm.ParentalControls.SessionLimits.xml),
[builder/limit API](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent/session-limits.h),
[calculation](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent/session-limits.c)
and [estimates](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml).
The live backend stays daily-only; the in-memory window has no grant, avoiding
native combined schedule/grant arithmetic across midnight/DST.

GNOME 50.6's [ScreenShield](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/screenShield.js)
emits lock completion synchronously; its
[ScreenSaver API](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/shellDBus.js)
uses the same shield. The design observes existing signals and calls public
methods. Qualify that ordering on each supported Shell, rather than assuming
an unavailable native feature.

Implementation must update specification, broker, state, screen-time, lifecycle
and removal owners. Use bounded, non-identifying guard/save diagnostics.
Engineering checks cover validation/migration, authorization, timezone endpoints,
native-builder membership, read budgets, per-child revisions, prompt-spanning
midnight, all save/rollback/crash stages and grant/revocation races.

Installed acceptance must cover:

- Bedtime locking with unused allowance; fresh-login/unlock denial; morning
  return; fixed/rest-of-day grants and revocation through public actions.
- Different weekday/weekend windows, full-day continuity, both DST directions,
  grants issued yesterday before today's opening, and independent children.
- Direct logind Unlock/ScreenSaver deactivation, an unlock animation crossing
  bedtime, startup crossing a boundary, and broker loss/timeouts during unlock.
- Suspend with ordinary lock-on-suspend disabled; recovery without automatic
  unlock; healthy in-window/grant-backed return with one authentication.
- Removal/reinstall retaining choices without native reactivation, followed by
  parent reapply without recreating grants.

Observe actual protected desktop/input outcomes, not only lock requests or logs.
Use engineering clock injection only in engineering checks; customer acceptance
follows the natural-boundary/public-action [test contracts](../TestAutomation/README.md).
This review implements nothing and claims no passing runtime acceptance.
