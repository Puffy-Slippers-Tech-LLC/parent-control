# Malcontent 0.14 integration note

Verified locally against Ubuntu's `malcontent` package `0.14.0-0ubuntu1.1`,
using the installed client implementation, manuals, daemon binaries, and GNOME
Shell's installed D-Bus interface use. Live system-bus introspection is blocked
in the development sandbox; that limitation is recorded in
`evidence/20260828T201750Z/`.

## Child request API

- Bus name: `org.freedesktop.MalcontentTimer1`
- Object path: `/org/freedesktop/MalcontentTimer1`
- Interface: `org.freedesktop.MalcontentTimer1.Child`
- Method: `RequestExtension`
- Input signature: `(ssta{sv})` — record type, identifier, duration seconds,
  extra data
- Output signature: `(o)` — request cookie/object path
- Response signal: `ExtensionResponse`, signature `(boa{sv})` — granted,
  cookie, extra data

For a device/session request, record type is `login-session` and identifier is
empty. Positive durations are arbitrary seconds. Duration zero asks the
extension agent to choose a duration (typically until the end of today), but
does not guarantee that result. The extension calculates the exact duration
to the next local midnight for its “Rest of the day” choice and sends that
positive value.

An approved positive duration replaces the active extension beginning at the
approval time. The selected value is therefore the new total remaining time,
not an amount added to the previously reported remainder. “Rest of the day” is
sent as the already-calculated interval to local midnight.

The request originates from the restricted user's system-bus connection. The
daemon identifies the caller and forwards it to
`org.freedesktop.MalcontentTimer1.ExtensionAgent` at
`/org/freedesktop/MalcontentTimer1/ExtensionAgent`. The packaged extension
agent requests the existing Polkit action
`org.freedesktop.Malcontent.SessionLimits.Extend`. The extension neither grants
time nor changes stored policy.

The native GNOME shield still uses this request API. The extension subscribes
to its responses and correlates their returned cookies.

The extension's combined time/app request cannot use `RequestExtension`
non-interactively: Malcontent 0.14 delegates its Polkit check to a separate
agent using a forwarded pidfd subject, which does not reliably consume a
temporary meta-action authorization created for the Shell's system-bus
subject. Making it interactive would add a second authentication dialog.

Instead, the combined action temporarily implies the two AccountsService
permissions `SessionLimits.ChangeOwn` and `AppFilter.ChangeOwn`. After the one
interactive combined check, the extension replaces the documented
`ActiveExtension` property `(tu)` with `(approval time, selected duration)` and
optionally writes the app filter. Both writes are non-interactive and originate
from the same GNOME Shell system-bus subject.

Malcontent 0.14 may not emit `EstimatedTimesChanged` after approving an
extension (upstream issue #133). GNOME Shell would otherwise retain its cached
`LIMIT_REACHED` state until another event, such as switching users, refreshes
it. Malcontent may also temporarily publish a stale estimate when concurrent
clients encounter its per-user database lock. For the lifetime of an
authenticated positive native `ExtensionResponse` or combined AccountsService
write, the extension replaces GNOME Shell's cached `currentSessionEnd` with the
approved expiry before its native state calculation runs. The approved value is
authoritative in both directions, so choosing a shorter duration replaces a
longer remainder instead of preserving it. This keeps the native manager
`ACTIVE` without auto-unlocking a manually locked screen. At expiry, the overlay
is removed and the authoritative estimate is refreshed.

The native shield's Ignore button uses the same response signal. The extension
observes a native click and accepts a response only when its cookie exactly
matches that shield's private request cookie. It records the daemon-supplied
`duration-secs`; unrelated system-bus responses are ignored.

`GetEstimatedTimes` can return `Error.Busy` while another supported client has
the user's timer database open. Estimate reads use bounded backoff for that
transient error and preserve the last successful estimate if all attempts fail.

The authenticated approval guard is persisted atomically in the child's user
data directory until its real-time expiry. The record contains only the issue
time, approved duration, and expiry; it is validated and bounded by the
original duration when loaded. This lets the grant overlay and additional
GDM-bypass re-lock guard survive a GNOME Shell/session restart without
contradicting a valid grant when Malcontent temporarily publishes a stale
estimate. Persistence uses public `Gio.File` and `GLib` APIs and does not alter
Malcontent's policy or authorization state. Like GNOME/Malcontent parental
controls generally, this user-owned extension and record are not a security
boundary against a technically advanced child account.
