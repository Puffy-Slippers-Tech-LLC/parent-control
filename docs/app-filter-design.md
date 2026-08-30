# Single authorization for time and app access

The request flow uses one custom Polkit meta-action which implies the two
privileged backend actions:

- `org.freedesktop.Malcontent.SessionLimits.Extend`
- `com.endlessm.ParentalControls.AppFilter.ChangeOwn`

The GNOME Shell extension first checks
`org.gnome.shell.extensions.request-more-time.ApproveTimeAndApps` with user
interaction enabled. It then calls both `RequestExtension` and `AppFilter.Set`
without `ALLOW_INTERACTIVE_AUTHORIZATION`, so only the meta-action can display
an authentication dialog.

## Why the authorization is retained briefly

Polkit evaluates an implied action by checking whether the same subject is
currently authorized for the meta-action. A plain `auth_admin` result is not
retained after the interactive check returns, so it cannot authorize the two
subsequent D-Bus calls. The combined action therefore uses `auth_admin_keep`.

The extension captures the temporary authorization ID and revokes it in a
`finally` block immediately after the two backend operations finish. Polkit
also scopes the authorization to the GNOME Shell subject. This gives the
sequential operations one approval without leaving the combined grant active
for Polkit's normal retention window.

The Malcontent extension agent runs in another process, but it is the trusted
mechanism checking authorization for the original GNOME Shell system-bus
subject. It does not check authorization for its own service user. Therefore,
the implied `SessionLimits.Extend` authorization applies to the request even
though the agent performs the check.

## App-filter semantics

The app filter remains a blocklist, represented as:

    AppFilter = (false, [blocked app targets])

When “Allow blocked apps during extra time” is checked, conditional targets
are omitted while permanent targets remain. When it is unchecked, both
conditional and permanent targets remain blocked. Other apps are allowed by
the blocklist automatically.

The policy file must be installed under `/usr/share/polkit-1/actions/`; bundling
it only with the user extension is not sufficient.
