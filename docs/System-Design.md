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
apps[desktop-id] = { state, targets[] }
request = { last_selected_duration, last_custom_minutes,
            allow_soft_blocked_apps }
```

App states are `allowed` (omitted when normalized), `permanent` (hard blocked),
and `conditional` (blocked unless a request allows soft-blocked apps).

Machine configuration is separate and contains only deployment values such as
the kiosk UID and request rate limit. It must not duplicate child preferences.

## Broker interface and roles

| D-Bus method | Child | Kiosk | Admin |
| --- | --- | --- | --- |
| `ListManagedUsers` | — | yes | yes |
| `GetPreferences` | own | selected child | selected child |
| `UpdateRequestPreferences` | own | selected child | selected child |
| `SetPreferences` | — | — | selected child |
| `SetParentControl` | — | — | selected child |
| `RequestAccess` | — | selected child | — |

Eligible children are local, interactive, non-system, non-admin accounts with
UID >= 1000, excluding the kiosk account.

`SetPreferences` cannot alter `parent_control_enabled`; only
`SetParentControl` owns extension lifecycle state. `RequestAccess` additionally
requires interactive Polkit approval and performs transactional
AccountsService updates with rollback.

## Main flows

1. **Manage:** Parent selects child -> reads preferences -> saves app policy or
   calls `SetParentControl`. Extension lifecycle succeeds before its flag is
   committed; commit failure triggers rollback.
2. **Child request:** Extension refreshes its own record -> uses saved request
   values and derived targets -> follows its existing in-session approval path.
3. **Kiosk request:** Kiosk loads/updates the selected child's request values ->
   calls `RequestAccess` -> broker authorizes and updates AccountsService.

## Installed layout

```text
/usr/bin/oh-no-parent-control                  kiosk launcher
/usr/bin/oh-no-parent-control-parent           parent launcher
/usr/libexec/oh-no-parent-control-broker       broker launcher
/usr/libexec/oh-no-parent-control-preserve-extension-state
/usr/lib/oh-no-parent-control/kiosk/            kiosk Python package
/usr/lib/oh-no-parent-control/parent/           parent Python package
/usr/lib/oh-no-parent-control/child/extension/ immutable extension payload
/var/lib/oh-no-parent-control/preferences/     authoritative child records
/var/log/oh-no-parent-control/<component>/     daily logs (10-day retention)
```

The broker is the sole log-file writer. Logs are owned by `root:sudo`: Ubuntu
administrators can read them, while other users cannot. Parent, child, and kiosk
send log events over the public D-Bus interface; caller-role checks prevent
components from writing into one another's folders. A component's first event
each day creates `YYYY-MM-DD.log` and removes that component's logs beyond the
newest 10 days.

Enabling Parent Control copies the immutable payload to the child's local
GNOME extension directory and enables its UUID. Disabling removes both.

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
