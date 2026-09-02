# Malcontent 0.14 integration note

Verified locally against Ubuntu's `malcontent` package `0.14.0-0ubuntu1.1`,
using the installed client implementation, manuals, daemon binaries, and GNOME
Shell's installed D-Bus interface use. Live system-bus introspection is blocked
in the development sandbox; that limitation is recorded in
`evidence/20260828T201750Z/`.

## Malcontent request API considered

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
does not guarantee that result. The product does not use this method for its
combined time/app request because it cannot make that operation one
broker-verified transaction.

An approved positive duration replaces the active extension beginning at the
approval time; it does not add to a previous active extension. Unused daily
allowance remains valid, so Malcontent permits access until the later of the
daily-allowance expiry and the active-extension expiry. For “Rest of the day,”
the product broker calculates the exact interval to the next local midnight
after approval and writes that positive duration directly to `ActiveExtension`.

The product's minute choices are explicitly additional time. Before writing a
new `ActiveExtension`, the broker queries usage through the authenticated
parent identity and applies its shared calculation:

```text
max(Daily allowance remaining, One-time grant remaining)
    + Additional one-time grant
```

For example, a 5-minute request with 32 minutes of effective backend time
remaining writes a 37-minute active extension. The parent status row and kiosk
request flow use the same broker-owned function. This conversion is not applied
to “Rest of the day”, which remains an absolute expiry choice.

The extension calls the product broker's `RequestOwnAccess` method. The broker
uses the extension's unique system-bus name only as the Polkit subject and
derives the target UID from its authenticated caller credentials. After one
non-retained product-action approval, the broker writes the documented
`ActiveExtension` property `(tu)` and the app filter as root, verifies both,
and rolls back both on failure. No Malcontent permission is implied or retained
in the child session.

After a broker-owned AccountsService write, the extension relies on Malcontent's
supported `EstimatedTimesChanged` signal and `GetEstimatedTimes` query. It does
not change GNOME Shell's private time-limit state or attach to the native lock
screen request flow.

`GetEstimatedTimes` can return `Error.Busy` while another supported client has
the user's timer database open. Estimate reads use bounded backoff for that
transient error and preserve the last successful estimate if all attempts fail.
