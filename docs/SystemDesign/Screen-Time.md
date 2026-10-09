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
banner visibility. Installed acceptance is queued, not implemented.

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
grant, PAM or fapolicyd mutation participates. Node cases cover timing, ownership
and client failure isolation; private-bus component cases exercise the real GJS
service and production suppression client with a persistent isolated GSettings
backend, including crash recovery and reacquisition after helper replacement.
These checks do not establish native GNOME banner or installed-system acceptance.

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

This operation reapplies the filter without terminating running applications.
It does not take the shared app-policy/grant/session-preparation transaction
lock. The Parent App serializes its own saves; request approvals separately
revalidate the saved preference snapshot around their asynchronous work.

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
and remains an error. Broker startup still requires successful activation.

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
deadline while a query is in flight. `NoReply`, `NameHasNoOwner`, and
`ServiceUnknown` trigger at most two further reads addressed to the same
well-known service name, allowing D-Bus activation to select its new owner.
All attempts share a 25-second budget inside the broker's 30-second helper
deadline, with 200 ms between attempts. Authorization failures and malformed
replies are not retried, and a failed read never becomes zero usage. The helper
is loaded on its next invocation (`none` activation); adapter logging changes
activate with the broker's `process-restart` classification.

The parent status client loads on the next Parent App launch (`none` package
activation). It reuses the existing `GetTimeStatus(uu) -> (uuuu)` contract and
needs no broker, Polkit, or saved-data change. Regression coverage in
[test_parent_client.py](../../tests/unit/test_parent_client.py) checks reads
without retained AccountsService authorization, fresh grant status, and error
propagation without sensitive logging. The broker role-revalidation regression
is in [test_core.py](../../tests/unit/test_core.py).

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

The public estimate API is `EstimatedTimesChanged` and `GetEstimatedTimes`.
Estimate reads use bounded backoff for `Error.Busy`, which can occur while
another supported client has the user's timer database open. The extension
does not modify GNOME Shell's private time-limit state or attach to the native
lock-screen request flow.

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
busy suffix; raw remote names, messages and stacks never enter events. New event
IDs preserve the historical field-free `child.estimate-failed` contract. The
shared catalogue and child enum validator must ship together with the broker;
child changes require session renewal and the broker loads the catalogue on
process restart. No saved-data migration is needed. Regression coverage uses
isolated Node adapter contexts and real GJS error classification; it does not
claim installed suspend/resume acceptance.

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
The former external helper ran before `pam_systemd`, when no session scope
existed, and could not modify the caller's PAM handle. Broker startup also
attempts to clear caps on existing managed graphical GDM sessions, requiring
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

The [package classifier](../../packaging/package_activation.py) gives PAM profile
and login-routing changes `reboot` activation. A replacement
`pam_oh_no_parent_control.so` alone requires `session-renewal`; the external
session-limit helper loads on each invocation (`none`). Extension-manager
changes activate at `process-restart`, and child-extension code at
`session-renewal`. A combined package takes every applicable impact. No
saved-data migration is needed for these integration changes. The PAM data
interface is documented in [pam_systemd](https://github.com/systemd/systemd/blob/main/man/pam_systemd.xml).

## Related design

- For authorization and grant commit/rollback order, read [Broker](Broker.md#authorization-and-grant-transactions).
- For app-policy restoration after unlock, read [Application policy](Applications.md#session-entry-reconciliation).
- For startup ordering or changed PAM/extension activation, read [Lifecycle](Lifecycle.md) and [Package update](../Publishing.md#package-update-activation).
