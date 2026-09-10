# Screen time and session limits

[System design overview](../System-Design.md)

Read this for daily limits, grant calculations, timer queries, child countdown,
GNOME locking, and PAM login/unlock checks.

Implementation: [core.py](../../broker/oh_no_parent_control/core.py), [extension_manager.py](../../broker/oh_no_parent_control/extension_manager.py), [remainingTimeIndicator.js](../../child/remainingTimeIndicator.js), [timerQuery.js](../../child/timerQuery.js), [session-limit helper](../../tools/session_limit_check.py), [PAM module](../../tools/pam_oh_no_parent_control.c).

## Screen-time model

`SetPreferences` cannot alter `parent_control_enabled`. `SetParentControl`
applies screen-time settings to the account and controls child-extension
activation when the saved toggle changes. `SetPreferences` can save a daily
limit value but does not apply it to Malcontent. Grant approval can also
initialize Malcontent `LimitType` and `DailyLimit`; see
[grant transactions](Broker.md#authorization-and-grant-transactions).
The daily limit is an integer from 0 through 1440 minutes; zero is grant-only
mode. App policy remains independent of whether the daily limit is enabled.

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
is in [test_core.py](../../tests/unit/test_core.py). See the
[2026-09-09 investigation](../Parent-Time-Status-Investigation-2026-09-09.md)
for observed failures, verification results, and installed-test limitations.

## Countdown and expiry enforcement

The child extension uses GNOME Shell's supported time-limit manager and the
public Malcontent estimate signal/query for the daily estimate. It passes that
estimate to `CalculateOwnRemainingTime`; the broker derives the child from the
caller and reads the live `ActiveExtension` itself. The panel counts down in
minutes and then seconds, preserving its last verified estimate across a
temporary read failure. At expiry, deduplicated diagnostics record whether the
estimate and daily limit are loaded, whether Shell is already in lock/greeter
mode, and whether a lock request is pending. These contain no account/session
identifiers; a separate fixed message records each actual Lock request.

The public estimate API is `EstimatedTimesChanged` and `GetEstimatedTimes`.
Estimate reads use bounded backoff for `Error.Busy`, which can occur while
another supported client has the user's timer database open. The extension
does not modify GNOME Shell's private time-limit state or attach to the native
lock-screen request flow.

At zero usable time the extension invokes the public GNOME ScreenSaver `Lock`
method and repeats enforcement if the retained desktop is unlocked without new
time. `pam_malcontent` independently denies a fresh login at zero. GDM unlocks
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

The PAM module/profile change activates at `reboot`; extension-manager changes
activate at `process-restart`, and child-extension diagnostics at
`session-renewal`. No saved-data migration is needed. The PAM data
interface is documented in [pam_systemd](https://github.com/systemd/systemd/blob/main/man/pam_systemd.xml).

## Related design

- For authorization and grant commit/rollback order, read [Broker](Broker.md#authorization-and-grant-transactions).
- For app-policy restoration after unlock, read [Application policy](Applications.md#session-entry-reconciliation).
- For startup ordering or changed PAM/extension activation, read [Lifecycle](Lifecycle.md) and [Package update](../Package-Update.md).
