# Single authorization for time and app access

The request flow uses one custom Polkit meta-action which implies the two
privileged backend actions:

- `com.endlessm.ParentalControls.SessionLimits.ChangeOwn`
- `com.endlessm.ParentalControls.AppFilter.ChangeOwn`

The GNOME Shell extension first checks
`org.gnome.shell.extensions.oh-no-parent-control.ApproveTimeAndApps` with user
interaction enabled. It then writes `ActiveExtension` and `AppFilter` through
AccountsService without `ALLOW_INTERACTIVE_AUTHORIZATION`, so only the
meta-action can display an authentication dialog. `ActiveExtension` is replaced
with `(approval time, requested duration)`.

## Why the authorization is retained briefly

Polkit evaluates an implied action by checking whether the same subject is
currently authorized for the meta-action. A plain `auth_admin` result is not
retained after the interactive check returns, so it cannot authorize the two
subsequent D-Bus calls. The combined action therefore uses `auth_admin_keep`.

The extension captures the temporary authorization ID and revokes it in a
`finally` block immediately after the two backend operations finish. Polkit
also scopes the authorization to the GNOME Shell system-bus subject. This gives
the sequential operations one approval without leaving the combined grant
active for Polkit's normal retention window.

Both properties are changed on the same system-bus connection used for the
combined check. This avoids Malcontent 0.14's delegated timer-agent check,
which represents the caller as a different Polkit subject and cannot consume
the combined authorization reliably. The app-filter write is skipped if its
target list is already correct.

## App-filter semantics

The app filter remains a blocklist, represented as:

    AppFilter = (false, [blocked app targets])

When “Allow blocked apps during extra time” is checked, conditional targets
are omitted while permanent targets remain. When it is unchecked, both
conditional and permanent targets remain blocked. Other apps are allowed by
the blocklist automatically.

The policy file must be installed under `/usr/share/polkit-1/actions/`; bundling
it only with the user extension is not sufficient.
