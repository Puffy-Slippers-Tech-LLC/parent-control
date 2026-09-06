# Broker, accounts, and authorization

[System design overview](../System-Design.md)

Read this for caller identity, D-Bus permissions, broker responsibilities,
approvals, revocation, and transaction rollback.

Implementation: [service.py](../../broker/oh_no_parent_control/service.py), [core.py](../../broker/oh_no_parent_control/core.py), [adapters.py](../../broker/oh_no_parent_control/adapters.py), [D-Bus contract](../../data/dbus-1/com.puffyslippers.OhNoParentControl1.xml), [Polkit integration](../../data/polkit-1).

## Runtime hierarchy and trust boundaries

Front ends do not read or write the private preference files. The parent reads
Malcontent usage and the AccountsService grant directly on its own system-bus
connection; Malcontent authorizes the usage query against the real administrator
caller. Runtime product policy changes and cross-account writes pass through
the broker. The system-bus policy permits callers to reach the service; the broker,
not possession of the bus name or a client executable, is the authorization
boundary.

## Broker layers

The broker is divided into these layers:

- `service.py`: service construction, startup reconciliation, D-Bus dispatch,
  asynchronous approval workers, and public error translation
- `core.py`: caller roles, target eligibility, validation, time arithmetic,
  serialization of approval/revocation, and rollback transactions
- `adapters.py`: caller credentials, AccountsService, Polkit, logind/systemd,
  and Malcontent timer access
- `preferences.py`: current schema, strict normalization, and atomic per-child
  storage
- `catalog.py`: launcher discovery in the selected child's XDG and system
  application directories, with native, Snap, or Flatpak target projection
- `execution_policy.py`: aggregate UID-scoped fapolicyd rule generation,
  replacement, activation, and rollback
- `app_termination.py`: UID-confined native, Snap, and Flatpak process discovery
  and termination, including desktop application scopes and their descendants
- `extension_manager.py`: safe per-child activation and runtime verification of
  the immutable GNOME extension payload
- `config.py` and `logs.py`: fail-closed machine configuration and broker-owned
  component logs
- `data_migration.py`: offline, version-stepped migration of saved application
  data before a new broker may start

## Accounts and roles

Candidate accounts are enumerated from current NSS identities so a newly
created local user can appear before first login. Accounts with a noninteractive
shell are excluded from the discovered lists. AccountsService is then the
authority for UID, local/system status, account type, lock state, display name,
and icon.

An eligible child is a local, non-system, non-administrator account with UID at
least 1000, excluding the configured kiosk UID. An eligible approver is a local,
non-system, unlocked administrator with UID at least 1000 and a username safe
for the Polkit identity rule. The broker reloads these account records rather
than trusting cached front-end labels or roles.

The dedicated kiosk UID is generated into the root-owned machine configuration
at installation. It is neither a child nor an administrator and may use only
the request-station operations allowed by the broker.

The Parent App's `.desktop` entry is owned by `root:sudo` with mode `0640`,
restricting its discovery to Ubuntu administrators. The executable launcher
is separately installed with mode `0755`. The Parent App checks the live
administrator role before showing its management window; the broker checks
management operations independently.

Management authorization uses the live AccountsService administrator flag and
also accepts UID 0. This is distinct from approver eligibility: root is not
listed as a selectable approver, and approvers must meet all the local-account,
unlocked-account, and username restrictions above.

## Broker interface and roles

The Admin column includes UID 0 for management authorization.

`own` means that the broker derives or verifies the child identity against the
calling UID. `selected child` means a caller may supply an eligible target UID;
the broker resolves and revalidates it.

| D-Bus method | Child | Kiosk | Admin |
| --- | --- | --- | --- |
| `ListManagedUsers` | - | yes | yes |
| `ListApprovers` | yes | yes | yes |
| `GetOwnAccount` | own | - | - |
| `GetPreferences` | own | selected child | selected child |
| `ListApplications` | - | - | selected child |
| `GetTimeStatus` | own | selected child | selected child |
| `CalculateRemainingTime` | own | selected child | selected child |
| `CalculateOwnRemainingTime` | own | - | - |
| `PrepareOwnSession` | own | - | - |
| `UpdateRequestPreferences` | own | selected child | selected child |
| `SetRequestMuted` | own | selected child | selected child |
| `SetPreferences` | - | - | selected child |
| `SetParentControl` | - | - | selected child |
| `RevokeOneTimeGrant` | - | - | selected child |
| `RequestOwnAccess` | own | - | - |
| `RequestAccess` | - | selected child | - |
| `LogEvent` | child component | kiosk component | parent component |

`LogEvent` is intentionally role-scoped: a front end cannot choose another
component's log, and no D-Bus caller may write the broker component log.

`SetRequestMuted` authorizes the target account as shown above and validates
`surface` as `child` or `kiosk`; it does not bind that value to the caller role.
The shared form selects its own surface. `CalculateRemainingTime` validates
caller-supplied arithmetic operands and returns a calculation; it does not
authorize or write a grant.

## Authorization and grant transactions

`RequestAccess` is restricted to the configured kiosk UID.
`RequestOwnAccess` derives its target from the child caller, and rejects a child
whose screen-time control is disabled. Both paths validate the requested
duration, approver, target, and saved preference snapshot before invoking a
dedicated interactive Polkit action.

The broker supplies the selected administrator username as an action detail.
The installed Polkit administrator rule restricts the challenge to exactly that
identity, so the standard agent shows one password prompt without a second
identity-selection page. The action uses `auth_admin`, implies no AccountsService
permission, and retains no reusable authorization in either front end. The
kiosk session runs the maintained MATE Polkit agent as a restartable user
service; agent failure denies the in-flight attempt without permanently ending
the request station.

An approved request initializes `DailyLimit` from saved preferences and enables
Malcontent limits if necessary before applying the filter and grant. Unlike the
child request, the kiosk request does not require `parent_control_enabled` to
be true. It does not change that saved toggle or activate the child extension.

After approval, the broker confirms that the requesting bus name still exists
and revalidates the child, approver, and preferences after authentication,
after the identity-scoped usage query, and immediately before writes. A
nonblocking broker lock permits only one app-policy save, approval, revocation,
or session-entry reconciliation transaction at a time. The per-caller repeat
interval is recorded only after a successful grant, so denial or cancellation
does not consume it.

For a request that keeps soft blocks enabled, the broker writes and verifies the
complete hard-and-soft filter, terminates matching apps owned by the selected
child, and writes `ActiveExtension` last. Native and Snap processes are pinned
with pidfds and signalled only after all four kernel-reported UIDs match the
child. Snap processes additionally match the kernel-applied
`snap.<instance>.<app>` AppArmor security label rather than the transient
executable path inside a mounted Snap revision. Flatpak instances are
enumerated and killed by instance ID using the child's
UID, primary GID, empty supplementary groups, and runtime directory. Every live
session for that UID is in scope; another user's process is never signalled.
When soft blocked apps are allowed, the broker installs the hard-only filter and
does not terminate any open process, including an already-open hard-blocked app.

Parent revocation uses the same process-ownership boundary. It restores and
verifies the complete filter, terminates matching apps for the selected child,
and clears `ActiveExtension` last. Reversible failure before termination
restores the complete old account state. Once termination may have changed a
process, that side effect cannot be rolled back; failure instead restores the
old time values, keeps the strict filter active, and reports the failure. A
rollback read-back failure is reported distinctly.

## Related design

- For grant arithmetic, read [calculations and usage identities](Screen-Time.md#grant-arithmetic-and-usage-identities); for screen-time activation, read [enablement](Screen-Time.md#screen-time-model).
- For termination matching, read [running application identity](Applications.md#running-application-identity); for expired grants at login/unlock, read [session reconciliation](Applications.md#session-entry-reconciliation).
- For preference fields being written, read [State](State.md).
- For file-log handling, read [Logging and feedback](Logging-and-Feedback.md#logging).
