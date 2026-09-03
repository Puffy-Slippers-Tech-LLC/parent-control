# System design

Oh No! Parent Control is three front ends around one privileged broker. The
broker owns per-child preferences and validates every cross-account operation.

## Repository map

```text
parent/   Administrator GTK app: child selection, enablement, app policy
child/    Managed-user GNOME Shell extension, assets, and extension policy
kiosk/    Dedicated GTK request-time station
broker/   Root system-D-Bus service, policy, storage, and OS adapters
data/     D-Bus, Polkit, systemd, desktop, and GNOME session integration
config/   Machine configuration example
tools/    Installation-time provisioning
tests/    Broker and kiosk unit tests
```

Entry points:

- Parent: `parent/oh_no_parent_control_parent/main.py`
- Child: `child/extension.js`
- Kiosk: `kiosk/oh_no_parent_control_kiosk/main.py`
- Broker: `broker/oh_no_parent_control/service.py`; policy is in `core.py`
- D-Bus contract: `data/dbus-1/com.puffyslippers.OhNoParentControl1.xml`
- Build and installation map: `Makefile`

## Runtime hierarchy

```text
Parent app ───────────────┐
Child extension ──────────┼── system D-Bus ──> root broker
Kiosk request station ────┘                       │
                                                  ├── per-child JSON preferences
                                                  ├── child extension lifecycle
                                                  ├── AccountsService/Malcontent
                                                  ├── fapolicyd execution rules
                                                  └── Polkit authorization
```

Front ends never share files directly. The root broker resolves caller UIDs,
reloads account data, validates targets, and owns these layers:

- `core.py`: caller roles, target eligibility, validation, and transactions
- `preferences.py`: schema normalization and atomic per-child storage
- `extension_manager.py`: install/remove and enable/disable child extension
- `adapters.py`: AccountsService, Polkit, caller credentials, user discovery
- `service.py`: thin D-Bus binding and error translation

## Shared state

The single preference source for child UID `N` is:

```text
/var/lib/oh-no-parent-control/preferences/N.json
```

The root-owned, mode `0600`, atomically replaced record contains:

```text
version
parent_control_enabled
daily_time_limit_minutes
apps[desktop-id] = { state, targets[], patterns[] }
request = { last_selected_duration, last_custom_minutes,
            allow_soft_blocked_apps, last_selected_approver_uid,
            kiosk_muted, child_muted }
```

App states are `allowed` (omitted when normalized), `permanent` (hard blocked),
and `conditional` (blocked unless a request allows soft-blocked apps).

Machine configuration is separate and contains only deployment values such as
the kiosk UID and request rate limit. It must not duplicate child preferences.

## Broker interface and roles

| D-Bus method | Child | Kiosk | Admin |
| --- | --- | --- | --- |
| `ListManagedUsers` | — | yes | yes |
| `ListApprovers` | yes | yes | yes |
| `GetOwnAccount` | own | — | — |
| `GetPreferences` | own | selected child | selected child |
| `ListApplications` | — | — | selected child |
| `GetTimeStatus` | own | selected child | selected child |
| `CalculateRemainingTime` | own | selected child | selected child |
| `CalculateOwnRemainingTime` | own | — | — |
| `UpdateRequestPreferences` | own | selected child | selected child |
| `SetRequestMuted` | own | selected child | selected child |
| `SetPreferences` | — | — | selected child |
| `SetParentControl` | — | — | selected child |
| `RequestOwnAccess` | own | — | — |
| `RequestAccess` | — | selected child | — |

Eligible children are local, interactive, non-system, non-admin accounts with
UID >= 1000, excluding the kiosk account.

`SetPreferences` cannot alter `parent_control_enabled`; only
`SetParentControl` owns extension lifecycle and the account's Malcontent daily
limit. Saving preferences immediately applies the configured app blocklist,
independently of the daily-limit state. Enabling applies the saved integer limit
of 0–1440 minutes; zero supports the product's grant-only mode. Disabling removes
the daily restriction and clears product-applied grants while retaining the
selected limit and reapplying the saved app filter.
Explicitly revoking a live one-time grant clears it and restores the saved app
filter. The managed child's extension consumes the resulting timer update and
uses GNOME's public screen-lock D-Bus API whenever the authoritative remaining
time is zero. The child supplies only its public timer estimate; the broker
derives the child UID from the D-Bus caller and reads the live grant itself.
The extension repeats lock enforcement if a retained desktop is unlocked,
without ending another user's foreground session on the shared display seat.
A later fresh login is evaluated against the remaining daily allowance by PAM.
The broker discovers launchers in the selected child's user XDG application
directories as well as the system directories. It turns each direct launcher
into the executable path (or Flatpak ref) used by Malcontent, so a per-user
AppImage is both displayed and restricted using its actual executable path.
When the parent saves an app policy, the broker resolves every selected desktop
ID against the child's current launcher again before applying and persisting
targets. This prevents an open parent window from saving a vanished executable
path after an application replaces a versioned AppImage during an update.
An app policy may also contain same-directory basename patterns such as
`/home/adrian/Applications/Lunar Client-*.AppImage`. These are compiled into
exact safe-file allowances followed by a UID-scoped fapolicyd directory denial;
therefore a newly downloaded matching AppImage is denied before reconciliation.
Conditional patterns are removed alongside their concrete target when an
approved extension allows soft-blocked apps.
Malcontent supplies the supported GNOME launcher policy but does not mediate a
trusted `.desktop` file opened directly from the desktop or Files. The broker
therefore mirrors native executable targets from each live AccountsService
blocklist into product-owned fapolicyd rules. Those UID-scoped execute denials
make registered launchers, desktop files, and direct executable launches obey
the same policy. Because fapolicyd 1.3 cannot quote whitespace in path rules,
such executable names use their SHA-256 object identity; ordinary paths use an
exact path rule. Missing saved targets need no current execution rule. Flatpak
refs remain enforced by Malcontent/Flatpak. The broker
reconciles the aggregate rules before accepting D-Bus calls and after the
broker changes an AppFilter. Rule replacement
and activation are transactional; a reload failure restores and reloads the
previous rules.
The packaged fapolicyd service drop-in keeps the daemon in its systemd
`activating` state until a root-owned canary execution is denied by the live
kernel policy. The display manager requires that completed startup, so no
managed graphical login can begin while fapolicyd is still rebuilding its
trust database after boot. If the readiness check fails, the login manager
fails closed instead of exposing an execution-policy gap.
`RequestAccess` and `RequestOwnAccess` require interactive Polkit approval and
perform transactional AccountsService updates with rollback. `RequestOwnAccess`
derives the target UID from the system-bus caller, so a child cannot name a
different target. The child and kiosk select a local interactive administrator
returned by `ListApprovers`.
The broker revalidates that account, passes its username as an action detail,
and an action-specific Polkit administrator rule limits authentication to that
one identity. The standard authentication agent therefore shows a password
dialog without a second identity-selection page. This remains one authorization
for the complete app-filter and ActiveExtension transaction. The request
actions use `auth_admin`, do not imply AccountsService permissions, and do not
retain a capability in either front end.
After approval, the broker launches a fixed-purpose, root-owned helper under the
selected administrator's UID and primary GID. The helper makes only the public
Malcontent parent usage query on a new system-bus connection and returns usage
intervals to the broker. The broker validates those intervals, calculates the
grant, revalidates both accounts, preferences, and the requesting connection,
and owns all writes.
This lets Malcontent see the authenticated parent as its actual D-Bus caller
without delegating any privileged write to the helper.
The kiosk session runs the maintained MATE Polkit agent as a restartable user
service. Authentication-agent failure denies the in-flight request but does not
end the kiosk session; systemd restarts the agent for a later request.

The broker is the single source of truth for the backend-compatible grant
formula:

```text
ActiveExtension = max(Daily allowance remaining, One-time grant remaining)
                  + Additional one-time grant
```

Malcontent authorizes its public parent usage API against the actual D-Bus
caller, so the parent app queries that API using the signed-in administrator's
connection. It reads the current one-time grant from AccountsService, derives
the unused daily allowance, and passes all three operands to
`CalculateRemainingTime`. The broker therefore remains the single source for
the formula, while Malcontent sees the real parent identity instead of the root
broker identity. For a child request, the broker performs that same
parent-identity usage query and calculation before writing the grant. The child
uses `CalculateOwnRemainingTime` when reconciling its displayed notification
countdown and zero-time lock. That method ignores any cached grant claim and
reads the current ActiveExtension through the broker.

## Main flows

1. **Manage:** Parent selects child -> reads preferences -> edits app policy at
   any time or calls `SetParentControl` with the daily-limit state and value.
   Every app-policy selection is saved immediately and applies its blocklist.
   Extension lifecycle and
   Malcontent account state succeed before preferences are committed; any
   failure restores the affected state.
2. **Child request:** The panel notification is unchanged. Clicking it launches
   the shared kiosk request GUI as a fullscreen overlay. The overlay locks the
   child selector to the signed-in account from `GetOwnAccount`, shares
   duration/approver/app-filter choices through the child's preference record,
   keeps a separate mute value from the kiosk station, and calls
   `RequestOwnAccess`. The broker derives the child from the caller, validates
   the request, authorizes only the selected administrator, and commits the
   verified time/app transaction. Cancel or Escape closes it.
3. **Kiosk request:** Kiosk selects a child and approving administrator, then
   loads/updates the child's request values -> calls `RequestAccess` -> broker
   authorizes the selected administrator and updates AccountsService. Escape
   matches Cancel and returns to the login screen when no authorization prompt
   is showing.

## Installed layout

```text
/usr/bin/oh-no-parent-control                  kiosk launcher
/usr/bin/oh-no-parent-control-parent           parent launcher
/usr/libexec/oh-no-parent-control-broker       broker launcher
/usr/libexec/oh-no-parent-control-query-usage  identity-scoped read-only helper
/usr/libexec/oh-no-parent-control-session-limit-check  PAM limit-state gate
/usr/libexec/oh-no-parent-control-execution-policy-ready  fapolicyd readiness gate
/usr/libexec/oh-no-parent-control-execution-policy-probe  deny canary
/usr/libexec/oh-no-parent-control-migrate-state saved-data migration runner
/usr/libexec/oh-no-parent-control-preserve-extension-state
/usr/lib/oh-no-parent-control/kiosk/            kiosk Python package
/usr/lib/oh-no-parent-control/parent/           parent Python package
/usr/lib/oh-no-parent-control/child/extension/ immutable extension payload
/var/lib/oh-no-parent-control/preferences/     authoritative child records
/var/log/oh-no-parent-control/<component>/     daily logs (10-day retention)
/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules generated execution denies
/usr/lib/systemd/system/{fapolicyd,display-manager}.service.d/
                                                  boot readiness ordering
```

APT and the full-machine installer stop the broker and run the packaged,
version-stepped migration framework before newly installed code can access
saved preferences. See `Data-Migration.md` for the schema contract and failure
recovery behavior.

The broker is the sole log-file writer. Logs are owned by `root:sudo`: Ubuntu
administrators can read them, while other users cannot. Parent, child, and kiosk
send log events over the public D-Bus interface; caller-role checks prevent
components from writing into one another's folders. A component's first event
each day creates `YYYY-MM-DD.log` and removes that component's logs beyond the
newest 10 days.

Enabling Parent Control copies the immutable payload to the child's local
GNOME extension directory and enables its UUID. Disabling removes both. Broker
startup republishes that payload for every preference-enabled managed child
before accepting calls. Package activation starts the broker when the payload
changes, so an already-running Shell may finish with its loaded code while the
next child session reliably loads the new per-user copy.
The PAM account stack exempts systemd, kiosk, and administrator accounts, then
uses the public AccountsService `LimitType` property to skip `pam_malcontent`
only when the account is confirmed unrestricted. Unknown or malformed state
continues through `pam_malcontent`; enabled zero-minute grant-only mode remains
enforced without showing the module's unrestricted-account message.

The Parent App desktop entry is `root:sudo`, mode `0640`.  GNOME therefore
indexes it only for Ubuntu administrator accounts; the launcher also verifies
broker administrator access before creating a window.  The broker remains the
authorization authority and rechecks the AccountsService role for every call.

The full-machine installer snapshots the invoking administrator's global GNOME
extension switch. A boot-time one-shot restores that exact value before GDM
starts, then deletes the snapshot. This prevents Ubuntu's Shell stop-timeout
fallback during the required reboot from changing an administrator preference;
an extension switch which was already off remains off.

## Design invariants

- One preference record per child; no preference files in user homes.
- All cross-account operations pass through the broker.
- Caller role and target eligibility are checked again immediately before
  privileged writes.
- Parent Control state changes only after extension lifecycle success.
- Kiosk behavior remains request-only; parent behavior remains management-only.
- The child extension has no independent preferences UI.
- The kiosk GTK request GUI is the single request form. The child session
  invokes that same GUI as an overlay; only the session backend differs.
