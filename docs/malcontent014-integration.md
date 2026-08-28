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
empty. Positive durations are arbitrary seconds. Duration zero is explicitly
handled by the daemon and its authorization message as “until the end of
today”; using that sentinel also leaves the local-timezone calculation with
Malcontent rather than duplicating it in the extension.

The request originates from the restricted user's system-bus connection. The
daemon identifies the caller and forwards it to
`org.freedesktop.MalcontentTimer1.ExtensionAgent` at
`/org/freedesktop/MalcontentTimer1/ExtensionAgent`. The packaged extension
agent requests the existing Polkit action
`org.freedesktop.Malcontent.SessionLimits.Extend`. The extension neither grants
time nor changes stored policy.

The implementation subscribes before submitting, correlates the returned
cookie, passes `ALLOW_INTERACTIVE_AUTHORIZATION`, and reports only a generic
failure in child-facing UI. Detailed errors use the extension log prefix.

