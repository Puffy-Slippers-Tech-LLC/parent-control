# Screen time and session limits

[System design overview](../System-Design.md)

Read this for daily limits, grant calculations, timer queries, child countdown,
GNOME locking, and PAM login/unlock checks.

Implementation: [core.py](../../broker/oh_no_parent_control/core.py), [extension_manager.py](../../broker/oh_no_parent_control/extension_manager.py), [remainingTimeIndicator.js](../../child/remainingTimeIndicator.js), [timerQuery.js](../../child/timerQuery.js), [session-limit helper](../../tools/session_limit_check.py), [PAM module](../../tools/pam_oh_no_parent_control.c).

## Screen-time model

### Remaining-time notifications

The child extension's [notification controller](../../child/remainingTimeNotifications.js)
uses the same verified total usable balance as the panel and expiry enforcement.
It loads the child's persistent [reminder settings](State.md#persistent-and-derived-state)
on enable, after language refresh on session resume, and when the request overlay
exits. Preference failures retain the last successful configuration and use the
ordinary error report; notification failure never stops countdown or locking.

Reminders fire once when remaining time crosses a configured threshold. The
timer schedules custom thresholds between normal panel updates, including
second-based values above a minute. A renewed balance above a threshold rearms
it; a two-second tolerance prevents repeated notifications from estimate wobble.
Renewed usable time clears the previous warning immediately.
Changing a reminder's threshold rearms that ID for its new time; text-only edits
and equivalent minute/second values retain delivery to avoid replaying a warning.
Startup does not replay past thresholds. A delayed tick crossing multiple
thresholds emits only the nearest crossed reminder. At zero, while locked or on
the greeter, notifications are cleared and no new reminder is emitted. Disabling
the extension cancels pending preference reads and destroys its owned source.

`show_in_fullscreen` chooses GNOME Shell `CRITICAL` urgency when true and `HIGH`
when false. The shared [banner renderer](../../child/reminderBanner.js) owns
presentation and fullscreen suppression using Shell's notification model and
[top-chrome API](https://raw.githubusercontent.com/GNOME/gnome-shell/50.0/js/ui/layout.js).
It follows the focused application's active monitor, falling back to the active
primary monitor or first active display when focus is unavailable. Fullscreen
suppression uses that display's state. This includes external-only configurations;
display and focus changes reposition the current banner without restarting its
deadline. Banner and tooltip chrome sit above application window groups.
Its notification model is not registered with Shell's message tray. The public
top-chrome layer also sits above override-redirect fullscreen windows.
Visible banners also temporarily inhibit compositor bypass through Mutter's
public API; their visibility and disposal lifecycle balances that owned hold.
Notifications use the product logo, user privacy scope, plain text and transient
lifetime. A later reminder replaces the previous product notification so an
undismissed critical banner cannot obstruct later reminders. Default content
combines shared localized minute/second plurals with `%(time)s left` in all
supported languages. For thresholds below 60 seconds, the controller queries
`GetOwnSessionAllowsSoftApps()` before delivery and uses
`%(time)s left, save your games!` when soft apps are currently allowed.
The broker compares the live filter with the saved hard-only and strict filters;
when these are identical, it uses the remembered choice with an active grant.
Policy-read failure reports the error and retains the plain time warning.
Locking, renewed time, preference changes and shutdown invalidate pending
deliveries. Custom text bypasses translation and markup parsing.
While a default reminder remains open, its body follows the verified live balance
without replacing or reissuing the notification. Minute reminders round up to
whole minutes, then switch to seconds below one minute; second reminders update
each second. The soft-app policy is also queried when an open minute reminder
crosses below one minute. Delayed policy replies use the latest balance, and
language refresh retains that balance. Editor previews retain their draft duration.
The [Application UI API](../TestAutomation/Application-UI-API.md#child-panel)
exposes current notification content and urgency; it does not claim native
banner visibility or installed acceptance.

### Native Wellbeing banner suppression

The extension's [suppression client](../../child/wellbeingSuppression.js) reads
Shell's `dailyLimitTime` and `getCurrentTime()` directly, independently of the
broker-adjusted panel balance. A nonempty loaded reminder list and active
parental-control limits enable the window `55 < remaining <= 65` on an unlocked
desktop. Reminder thresholds, custom text and fullscreen preference do not
change eligibility. GNOME 50's private 60-second warning threshold and the
five-second margin are named constants in [window/lease logic](../../child/wellbeingLogic.mjs);
Shell exposes the deadline but no public warning-threshold setting.
Signals and a separate one-second timer reevaluate eligibility. Login/resume
inside the window uses its remainder; a missed window below 55 seconds is not
replayed. No private notification objects or enforcement state are modified.

The unprivileged [session service](../../child/wellbeingService.js) exclusively
owns the Wellbeing application's `show-banners` override. A session-bus method
accepts only a finite expiry up to ten seconds away, or zero for cancellation.
Independent sender/instance leases share one original snapshot; the last release
restores it. A new enable gets a fresh token, so an old instance's late cancellation
cannot release its replacement. The service accepts at most 64 concurrent leases.
Unique bus-owner loss releases a crashed Shell's leases. Both real-time and
monotonic deadlines bound a lease, checked every 250 ms while work is pending.
The client watches the service's unique bus owner, invalidates acknowledgements
on replacement, and reacquires an eligible window. Requests pin a known owner;
late replies from a previous owner cannot acknowledge the replacement. Eligibility
is reevaluated before reacquisition. Shutdown detaches the watch and serializes
cancellation after in-flight calls without activating a helper for cancellation.
Asynchronous failures and reporting failures do not escape into extension startup
or enforcement.

Before suppression, the service saves and synchronizes the original explicit
boolean or unset/default state in the child schema's `wellbeing-banner-backup`.
Restoration synchronizes before clearing that record. User banner edits during
the window are deliberately overwritten; unrelated notification settings are
untouched. Invalid recovery records refuse new suppression. Failed restoration
retains the record and retries. A user systemd unit starts independently of the
extension at user-manager startup, restarts on failure and recovers before new
leases. Session D-Bus activation also starts it on demand. Ordinary termination
restores; an uncatchable crash is recovered by restart or next login. Disabled
services, unavailable settings backends or locked keys can delay recovery.
Both activation routes use the same fixed native launcher. It retains ordinary
users' environment, including `DCONF_PROFILE`, `XDG_CONFIG_HOME` and
`GSETTINGS_BACKEND`, so the helper accesses the same settings as their session.
Only the dedicated kiosk UID receives the restricted startup environment.

Child diagnostics record eligibility transitions, acquisition/cancellation,
helper-owner changes, stale replies, shutdown and failures through the approved
`child.wellbeing` event. The independent helper writes fixed `onpc.child`
journal messages for settings backup, suppression, restoration and verification,
lease expiry/release, sender loss, invalid requests, capacity and recovery retries.
Repeated helper failures are suppressed per stage until recovery; healthy timer
ticks produce no logs. These messages contain only shipped categories and the
original boolean/default category, never identities, tokens, deadlines, reminder
content or exception text. Helper journal messages are local diagnostics and are
not automatically included in feedback exports.

This is best-effort presentation suppression: queued banners and startup races
can escape, and other noncritical Wellbeing banners share the window. An eligible
saved reminder need not actually be visible. No broker/AccountsService policy,
grant, PAM or fapolicyd mutation participates.
Engineering checks do not establish native banner or installed-system acceptance.

`SetPreferences` cannot alter `parent_control_enabled`. `SetParentControl`
applies screen-time settings to the account and controls child-extension
activation when the saved toggle changes. `SetPreferences` can save a daily
limit value but does not apply it to Malcontent. Grant approval can also
initialize Malcontent `LimitType` and `DailyLimit`; see
[grant transactions](Broker.md#authorization-and-grant-transactions).
The saved-data validator and broker accept integer daily limits from 0 through
1440 minutes; zero is grant-only mode. The current Parent App's public editor
has a narrower range: custom values are 0–1439, with presets 0, 15, 30, 45,
then half-hour increments from 60 through 1410. It does not offer a 1440-minute
choice. These UI and storage/API bounds must not be conflated in customer tests.
App policy remains independent of whether the daily limit is enabled.

The package installs the extension system-wide so every GNOME Shell discovers
it during startup, while the broker controls activation independently for each
child. Enabling from the disabled state enables the child extension through
GNOME Shell's supported `gnome-extensions` interface when a live Shell owns it
(and through durable offline settings otherwise), clears stale
`ActiveExtension`, applies the selected daily limit, and reapplies the complete
saved app blocklist. Changing the limit while already enabled preserves the
current grant. Disabling deactivates the extension, clears the daily restriction
and current grant, retains the configured choices, and reapplies the saved app
blocklist. Account writes are read back before committing the preference record;
extension transitions also verify GNOME's configured and active state. Failures
restore the prior state. Live activation is accepted only when
GNOME Shell reports the extension both enabled and active; deactivation is
accepted only when it reports neither. Offline activation is verified against
the durable settings that Shell will consume at next login.
After a verified live transition, the broker allows up to four seconds for
Shell's asynchronous settings write to become visible. It only rereads settings
during that wait, then rechecks runtime state before accepting the transition.
Persistent disagreement and failed reads retain the normal failure and rollback.

Native time transitions use the public `DailySchedule=(0,86400)` and schedule-only
`LimitType=1` as a verified temporary bridge. This keeps usable time while a
grant is cleared or restored, without publishing disabled limits with a current
grant. Unlike a fixed 24-hour daily allowance, the full-day local schedule also
covers a 25-hour day. Transactions snapshot the original schedule along with
the type, daily allowance and grant; rollback restores all four and verifies
safety-critical writes before dependent effects. A failed rollback remains an
error.

The kiosk-only API can create a native grant while the saved toggle is off,
as described in [grant transactions](Broker.md#authorization-and-grant-transactions).
A same-disabled save with a current native grant refuses before effects: it
cannot both retain that grant and safely publish disabled native limits.
Ordinary already-disabled saves and same-enabled grant retention are unchanged.

This operation reapplies the filter without terminating running applications.
It shares the app-policy/grant/session-preparation transaction lock through
native snapshots, writes and rollback. An approval cannot capture a temporary
bridge or publish a grant after a concurrent disable. The Parent App serializes
its own saves; request approvals also revalidate the saved preference snapshot
around their asynchronous work.

Shell availability checks ownership of `org.gnome.Shell`. The separate
`org.gnome.Shell.Extensions` proxy service starts on demand; its absence must
not select offline activation for a running desktop. The supported CLI still
performs activation and configured/active verification.

GNOME may turn on `disable-user-extensions` after a session startup failure.
Startup reassertion for a saved enabled child restores that global switch to
false and verifies the write before proceeding. Ordinary preference transitions
retain their refusal while the global switch is disabled, so a later failed
preference transaction cannot leave a global switch change behind. Individual extension choices
are preserved; this also resumes other individually enabled extensions. A
failed activation restores the switch and original lists, verifies rollback,
and remains an error. Startup isolates failed child account/home validation and
retains its diagnostics without changing saved controls or live enforcement;
shared extension dependencies still gate readiness. A broker restart retries
enabled children after the unavailable integration is restored.

## Grant arithmetic and usage identities

Malcontent replaces an active extension starting at approval time rather than
adding to it; unused daily allowance remains valid. The product does not use
Malcontent's `RequestExtension` method because its combined time/app approval
requires one broker-verified transaction. It writes the public AccountsService
`ActiveExtension` property `(tu)` directly with a positive duration.

For fixed-duration requests, the broker computes the duration stored in
`ActiveExtension = (issued_at_epoch_seconds, duration_seconds)` as follows:

```text
duration_seconds = max(Daily allowance remaining, One-time grant remaining)
                  + Additional one-time grant
```

The Parent App uses `GetTimeStatus` for the remaining operands and calculated
total. It does not read the AccountsService grant directly: cross-account
`SessionLimits.ReadAny` requires Polkit authentication, so a periodic direct
read can fail when no retained authorization is available. The broker owns the
read and calculation under the authorization boundary described below.
For a fixed-duration request, the broker launches the fixed-purpose
`oh-no-parent-control-query-usage` helper under the authenticated approver's UID
and primary GID. The helper opens a new system-bus connection and returns only
usage intervals; the root broker validates them and owns every write. A
rest-of-day request instead computes the seconds to the next local midnight with
timezone-aware epoch arithmetic.

Rest-of-day replaces the current grant with that midnight deadline; it does
not take the maximum with an existing later expiry. Fixed requests can carry
past midnight. Grant time is elapsed wall-clock time, including time spent
locked, signed out, suspended or powered off, rather than a paused usage bank.
The broker captures issuance time before applying account changes and stopping
required apps. `ActiveExtension` is written last, but the duration is already
running by then; completion and the UI confirmation do not reset its start.

Daily usage calculations clip intervals to the current local day and current
time and merge overlaps before subtraction, so concurrent/overlapping recorded
intervals are not counted twice. Unavailable usage is an error, not zero use.

For `GetTimeStatus`, the broker first validates the caller and selected child,
then runs the same fixed-purpose usage helper as that child to read only its own
usage. Malcontent's public `QueryUsage` implementation permits self-reads and
parent reads, but explicitly rejects UID 0. No administrator identity is selected
on behalf of a child or kiosk status request. Approval-time usage queries retain
the authenticated approver identity described above.

The helper tolerates the timer daemon exiting normally at its inactivity
deadline while a query is in flight. `NoReply`, `NameHasNoOwner`,
`ServiceUnknown`, and local/remote timeout errors trigger at most two further
reads addressed to the same well-known service name, allowing D-Bus activation
to select its new owner. The exact timer `Parent.Error.Busy` response uses backoff of
100, 250, 500, 1000 and 2000 ms, with at most six total attempts. Mixed failures
share attempt indices and one 25-second monotonic budget inside the broker's
30-second helper deadline; each call has at most five seconds. Other transient
reads wait 200 ms. An overdue retry never dispatches another read.
Authorization failures and malformed replies are not retried, and a failed
read never becomes zero usage. Fixed private helper exit statuses retain the
final reviewed timer category in `adapters.usage-query-failed`, while preserving
the broker's backend-unavailable result. No raw exceptions, remote names or
identities cross that diagnostic boundary. The helper
is loaded on its next invocation (`none` activation); adapter logging changes
activate with the broker's `process-restart` classification.

Parent retains the `GetTimeStatus(uu) -> (uuuu)` status contract.

## Countdown and expiry enforcement

The child extension uses GNOME Shell's supported time-limit manager and the
public Malcontent estimate signal/query for the daily estimate. It passes that
estimate to `CalculateOwnRemainingTime`; the broker derives the child from the
caller and reads the live `ActiveExtension` itself. The panel counts down in
hours/minutes (compact hours or minutes on a vertical panel), then seconds at
60 seconds or less, preserving its last verified estimate across a
temporary read failure. At expiry, deduplicated diagnostics record whether the
estimate and daily limit are loaded, whether Shell is already in lock/greeter
mode, and whether a lock request is pending. These contain no account/session
identifiers; a separate fixed message records each actual Lock request.
The tooltip retains the full time explanation on compact panels, displaying
`HH:MM:SS` and counting down every second. The
[right-click preference](Frontends.md#child-panel-preference) controls only
countdown effects, not the estimate, request action or enforcement.

During uninterrupted active use, Shell's finite positive `dailyLimitTime`
supplies the countdown deadline, including at expiry. Fresh Malcontent reads can
omit ongoing usage until it is checkpointed, so taking the later deadline would
restart the displayed countdown on every query. When Shell has no active
deadline, the public timer estimate supplies the recorded-use fallback. Daily
accounting must preserve inactive intervals; a deadline cached before inactivity
is not a fresh resume balance. The broker still reads the live grant and selects
the longer remaining amount.

GNOME Shell 50.1 and 50.5 do not refresh their cached parental-controls deadline
on resume, and the native dispatcher can lock using that stale deadline. The
[resume estimate controller](../../child/resumeEstimateRefresh.js) observes the
manager's public `dailyLimitTime` notifications (zero while inactive), rather
than implementing another activity tracker. At inactivity/resume boundaries,
the existing [timer client](../../child/timerQuery.js) self-reads `QueryUsage`
and replays one complete returned interval, with identical endpoints, through
`RecordUsage`. Malcontent's documented overlap merging preserves accounting;
its normal `EstimatedTimesChanged` signal refreshes Shell as well as the panel.
No empty transaction, invented use, policy change or private Shell mutation is
used. The relevant public contracts are
[QueryUsage](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Parent.xml)
and [RecordUsage](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml).

While inactive, the controller repeats before the cached deadline can expire,
at half the returned remaining time with a 60-second maximum and subsecond
scheduling near expiry. This is necessary because Shell also evaluates its old
deadline during inactivity. A zero balance stops this maintenance until a native
policy/state change, including the daily reset. Delayed estimate notifications
do not rearm an exhausted balance or create a replay feedback loop.
Continuous activity never repeats usage writes or retries
a failed resume write: either would omit ongoing uncheckpointed use and restart
the countdown. Activity/limit changes cancel obsolete reads before a write;
shutdown cancels pending work and removes the controller's signals and timer.
Disabling limits discards coalesced work before any later active enable.
Cancellation prevents obsolete dispatch; it cannot retract an already dispatched
D-Bus write. That write still contains only the identical recorded interval.
The workaround remains asynchronous and cannot guarantee cache refresh during
timer-service unavailability or make native deadline evaluation atomic with resume.
Transient inactive failures back off and open the existing child error reporter
after three consecutive failures while continuing recovery. A transient
`QueryUsage` or `RecordUsage` boundary failure with a finite positive native
deadline retains that countdown, records `child.resume-refresh-deferred`, and
waits for the next inactivity transition
without opening a reporter or replaying usage late. Repeated active failures at
the same operation stage open one report from the third occurrence, without
retrying a usage write during active use. Healthy idle refreshes do not erase
this resume-only failure evidence; a complete successful active refresh or limit
lifecycle change resets it. Ordinary countdown reads retry and report exhausted
failures independently, but do not establish that usage query/replay is healthy.
Permanent resume refresh failures, exhausted estimate reads, and failures
without a finite native deadline use the existing child error reporter
immediately. Only the daemon's exact `Child.Error.Busy` and
`Parent.Error.Busy` names are treated as contention; unrecognized remote names
remain errors. These are the names registered by the daemon's
[Child service](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/child-timer-service.c)
and [Parent service](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/parent-timer-service.c).
This is a product compatibility workaround for the native cache
defect, not a GNOME source fix or a second accounting/enforcement implementation.
Remove it when the supported Shell implementation refreshes estimates before
evaluating inactivity/resume deadlines.

The public estimate API is `EstimatedTimesChanged` and `GetEstimatedTimes`.
Estimate reads use bounded backoff for `Child.Error.Busy`, which can occur while
another supported client has the user's timer database open. The extension
does not modify GNOME Shell's private time-limit state.

The read-only [session observer](../../child/sessionDiagnostics.js) records native
lock decisions alongside logind activity, idle and locked hints and Shell's
locked/greeter mode. It observes only the current session's logind proxy, checks
the signal sender against its current bus owner, and records each `Unlock`
request separately from its result one second later. Native state transitions
between those observations are retained. Grant changes and these observations
never request an unlock, replay authentication or alter enforcement. See the
[diagnostic contract](Logging-and-Feedback.md#native-login-and-unlock-observations).

GNOME Shell 50.6 has a separate retained-session admission limitation after
exhaustion. Its [_updateState implementation](https://github.com/GNOME/gnome-shell/blob/50.6/js/misc/timeLimitsManager.js#L973-L993)
retains `LIMIT_REACHED` while inactive even when a new estimate has positive
time. Its [ScreenShield unlock guard](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/screenShield.js#L515-L520)
can therefore refuse GDM's authenticated unlock before the activity transition
clears that state. The desktop remains locked and another credential can succeed.
Refreshing estimates alone does not correct that state transition. The existing
resume-estimate workaround does not fix this admission defect.

The [unlock continuation](../../child/sessionUnlock.js) addresses this race in
the child extension. It arms only for an `Unlock` signal from the current
session proxy's current logind owner when the native parental-controls state
is `LIMIT_REACHED` and the child desktop is locked. A grant or positive estimate
by itself cannot arm it. The original request lasts at most two monotonic
seconds. Once that same session is active, native state is `ACTIVE`,
`shouldLockSession` is false and its finite native deadline is still positive,
one idle callback invokes the public `ScreenShield.deactivate(false)` method.
This is the same entry point used by GNOME's logind handler; its final native
guard remains authoritative. The invocation runs in Shell's main loop,
so there is no extra bus hop before dispatch. No native method is replaced,
no private state is written and no credential is received or replayed.
The native positive deadline already incorporates GNOME's aggregate user activity;
a potentially delayed per-session idle hint is diagnostic, not another admission gate.

Before dispatch, a newer logind Lock, suspend, owner replacement, session departure after
activation, disabled parental limits, greeter transition, renewed exhaustion
after the native decision cleared, or extension shutdown cancels the request.
A newer authorized Unlock replaces it with a separate bounded request. The
deadline is checked again at dispatch in case the timer is delayed. Each request
can continue only once. An observed native unlock or native unlock animation
retires pending authority synchronously, before a direct ScreenSaver/shortcut
relock can reuse it. These direct lock routes do not emit logind's Lock signal.

The native call can defer completion for authentication messages and animation.
It exposes no public cancellation handle. Handoff consumes the controller's
authority permanently; GNOME's existing authentication/lock ordering owns the
native operation from that point onward. A returned method is not considered
success until public `locked` becomes false. The controller observes for another
two seconds; later interruptions and observation expiry are diagnostic, not a
claim that native callbacks were cancelled. No private callback manipulation or
unlock/relock cycle attempts to alter that native behavior. Native failure or
pre-dispatch expiry retains ordinary authentication and enforcement.
Both observer and continuation are excluded from nested previews, which have
no owned logind session. Installed single-entry return after a grant still
requires validation in a renewed child session.
Remove this compatibility controller when supported Shell versions refresh the
native admission decision before processing logind's Unlock.

The child estimate client also retries `NoReply`, `NameHasNoOwner`,
`ServiceUnknown`, and local/remote timeout errors, covering timer-owner loss
around idle shutdown and suspend/resume. Each retry addresses the well-known
service name so D-Bus activation can select its new owner. These failures allow
at most three attempts; busy backoff retains at most six total attempts. Mixed
failures share those attempt indices and one 25-second monotonic budget, with
each call limited to five seconds. Authorization, invalid arguments and unknown
errors are not retried. A successful recovery updates the countdown without
opening the reporter; exhausted retries retain the previous verified estimate
and report the failure. No failed read becomes zero remaining time.

Diagnostics record a closed error category, attempt number, retry decision and
successful recovery. Terminal refresh diagnostics distinguish the timer read,
local allowance calculation and broker calculation, plus loaded/locked/greeter
booleans. Categories come only from Gio error domains/codes or the recognized
timer Busy names; raw remote names, messages and stacks never enter events. New event
IDs preserve the field-free `child.estimate-failed` contract. The
shared catalogue and child enum validator must ship together with the broker;
child changes require session renewal and the broker loads the catalogue on
process restart. No saved-data migration is needed; local checks do not establish
installed suspend/resume acceptance.

The [locked-session focus controller](../../child/lockedSessionFocus.js) owns a
GNOME 50 compatibility workaround for keyboard-device reactivation. Mutter can
restore the remembered client surface while Shell's lock grab remains active.
An after-handler for the default Clutter seat's `device-added` signal runs after
Mutter enables keyboard capability. For a keyboard-capable device, a locked
non-greeter session and an existing stage grab, it re-notifies the public
`is-grabbed` property so Mutter reapplies its existing device-focus policy.
It creates no grab, changes no actor focus and never unlocks or relocks. This is
not a dedicated Clutter focus-resynchronization API; it is qualified against the
supported GNOME 50 implementation. The synchronous hook is independent of panel
visibility, prevents reentrant notification, and disconnects on failed extension
startup or disable. It owns no idle or deferred callback. The
`child.lock-focus-sync` diagnostic records only a closed completion/failure
outcome; device, window, account and session identities are excluded.

Once an estimate has been successfully loaded, at zero usable time with a daily
limit enabled the extension invokes the public GNOME ScreenSaver `Lock` method.
It reevaluates enforcement when the retained desktop is unlocked without new
time. Grant expiry alone does not lock a desktop with daily time remaining.
An initial failed estimate read is reported; the extension does not treat the
uninitialized zero as confirmed exhaustion. `pam_malcontent` independently
denies a fresh login at zero. GDM unlocks
an existing session through PAM authentication without repeating PAM account
management, so the product PAM profile applies Malcontent's public remaining-
time check to `gdm-password` authentication as well. A confirmed zero-time
result uses PAM's public `PAM_ACCT_EXPIRED` status, which GDM renders as its
localized time-limit explanation; an indeterminate check remains fail-closed
without being mislabeled as confirmed exhaustion. This closes the retained-
session path while preserving active one-time grants; the kiosk and Ubuntu
administrator accounts bypass this authentication check in the PAM profile;
the helper also permits UID 0. Because Malcontent's login-time `RuntimeMaxSec`
snapshot would terminate a live session after a later grant, the native product
PAM account module follows `pam_malcontent` and replaces its documented
`systemd.runtime_max_sec` PAM data with `infinity` before a GDM session opens.
It leaves the timer intact for terminal, SSH, and other PAM services where the
GNOME screen-lock enforcement is unavailable.
This prevents even a one-second grant from creating a kill timer while GNOME
starts. The account check's denial remains authoritative; exempt and confirmed
unrestricted accounts skip both modules, and other resource limits are preserved.
Broker startup also attempts to clear caps on existing managed graphical GDM
sessions, requiring
logind's user class, Wayland/X11 type, and GDM service. Expiry therefore locks the
child instead of logging out that child or
ending another user's foreground session. Expiry does not itself terminate
applications. On each new child session and each transition from locked to
unlocked, the child component invokes the broker-owned `PrepareOwnSession`
reconciliation in [Application policy](Applications.md#session-entry-reconciliation);
the unprivileged component neither decides whether a grant is current nor
signals processes itself.
Session preparation is asynchronous: it is not a compositor admission barrier.
Failures are reported and preparation is retried while the desktop is usable.

Administrative access to an existing user bus must also work at zero time.
Systemd's `systemctl --user --machine=UID@` transport starts a transient system
service running `systemd-stdio-bridge --user --quiet` with `PAMName=login`.
The shared session-limit helper exempts only that transport from the two product
time modules. It requires real and effective UID 0, the exact `login` PAM service,
a verified non-kiosk account, and the system manager's public `GetUnitByPID` and
service properties binding its still-live parent to the matching `MainPID`,
target user and exact bridge executable/arguments in a transient unit. The
executable field may be the native transport's preserved basename
`systemd-stdio-bridge` or `/usr/bin/systemd-stdio-bridge`; other relative and
absolute paths are rejected. An unverifiable identity, changed command or failed
query retains enforcement.
Other PAM modules and kiosk admission still run; ordinary terminal/SSH logins
and GDM login/unlock retain their time checks. This avoids Fedora's native
package triggers failing to reach an exhausted child's manager with
`Failed to start jobs: Transport endpoint is not connected`. The helper loads
the change on its next invocation (`none`), on both Ubuntu and Fedora, without
changing saved limits or restarting user managers.

The [package classifier](../../packaging/package_activation.py) gives the selected
PAM profiles and login helper next-invocation activation (`none`). A replacement
`pam_oh_no_parent_control.so` requires `session-renewal`; the external
session-limit helper also loads on each invocation (`none`). Boot-order changes
and removed legacy manifest members retain their applicable reboot impacts under
the [lifecycle owner](Lifecycle.md#package-activation-and-session-renewal). Extension-manager
changes activate at `process-restart`, and child-extension code at
`session-renewal`. A combined package takes every applicable impact. No
saved-data migration is needed for these integration changes. The PAM data
interface is documented in [pam_systemd](https://github.com/systemd/systemd/blob/main/man/pam_systemd.xml).

## Related design

- For authorization and grant commit/rollback order, read [Broker](Broker.md#authorization-and-grant-transactions).
- For app-policy restoration after unlock, read [Application policy](Applications.md#session-entry-reconciliation).
- For startup ordering or changed PAM/extension activation, read [Lifecycle](Lifecycle.md) and [Package update](../Publishing.md#package-update-activation).
