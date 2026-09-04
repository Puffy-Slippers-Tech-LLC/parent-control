# System design

Oh No! Parent Control has three unprivileged front ends around one privileged
broker. The broker owns product policy, resolves every caller from system D-Bus
credentials, and validates every cross-account operation. AccountsService,
Malcontent, fapolicyd, systemd, PAM, and GNOME Shell provide the operating-system
enforcement mechanisms.

## Repository map

```text
parent/   Administrator GTK app: child selection, screen time, app policy
child/    Managed-user GNOME Shell extension: countdown, lock, request launcher
kiosk/    Dedicated GTK request station and the shared request form
common/   Shared GTK branding, About dialog, and user-icon helpers
broker/   Root system-D-Bus service, policy, storage, and OS adapters
data/     D-Bus, Polkit, systemd, PAM, desktop, and GNOME-session integration
config/   Machine-configuration example
tools/    Provisioning, session, execution-readiness, and package helpers
debian/   Debian package metadata and maintainer scripts
tests/    Host-safe unit tests and the disposable-VM integration harness
```

Entry points:

- Parent: `parent/oh_no_parent_control_parent/main.py`
- Child: `child/extension.js`
- Kiosk and child request overlay: `kiosk/oh_no_parent_control_kiosk/main.py`
- Broker: `broker/oh_no_parent_control/service.py`; policy is in `core.py`
- D-Bus contract: `data/dbus-1/com.puffyslippers.OhNoParentControl1.xml`
- Build and installation map: `Makefile`

## Runtime hierarchy and trust boundaries

```text
Parent app ───────────────┐
Child extension ──────────┼── system D-Bus ──> root broker
Kiosk request station ────┘                       │
                                                  ├── private child preferences
                                                  ├── AccountsService/Malcontent
                                                  ├── fapolicyd execution policy
                                                  ├── child extension lifecycle
                                                  ├── child-owned process termination
                                                  └── Polkit authorization
```

Front ends do not read or write the private preference files. The parent does
make a read-only Malcontent usage query on its own system-bus connection because
Malcontent authorizes that query against the real administrator caller. All
product policy changes and every cross-account write still pass through the
broker. The system-bus policy permits callers to reach the service; the broker,
not possession of the bus name or a client executable, is the authorization
boundary.

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
  and termination
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
the request-station operations allowed by the broker. The Parent App launcher
is owned by `root:sudo` with mode `0640`, so GNOME indexes it only for Ubuntu
administrators; the launcher and broker also recheck the live administrator
role before a management window or operation is allowed.

## Persistent and derived state

The single product preference source for child UID `N` is:

```text
/var/lib/oh-no-parent-control/preferences/N.json
```

The preference directory is root-only and each mode-`0600` record is validated
and atomically replaced. Its current logical schema is:

```text
version
parent_control_enabled
daily_time_limit_minutes
apps[desktop-id] = {
    state, targets[], patterns[], user_saved_match_rule
}
request = {
    last_selected_duration, last_custom_minutes,
    allow_soft_blocked_apps, last_selected_approver_uid,
    kiosk_muted, child_muted
}
```

App states are `allowed`, `permanent` (hard blocked), and `conditional` (soft
blocked). Normalization omits an allowed entry unless it carries a saved match
rule that must survive later policy changes.

Machine configuration is separate at
`/etc/oh-no-parent-control/config.json`. It contains only its schema version,
the kiosk UID, and the minimum successful-request interval; it does not
duplicate child preferences.

The ownership of runtime state is deliberately split:

| State | Authority | Purpose |
| --- | --- | --- |
| Configured screen-time and app choices | Product preference record | Durable parent intent |
| `AppFilter` | AccountsService | Live launcher/Flatpak blocklist derived from preferences |
| `ActiveExtension` | AccountsService | Current one-time grant |
| Usage intervals and estimates | `malcontent-timerd` | Measured daily use |
| UID-scoped native deny rules | fapolicyd | Live execution policy derived from `AppFilter` and saved patterns |
| Extension payload | System GNOME data directory | Immutable package content discovered when Shell starts |
| Extension activation | Per-account GNOME settings | Derived enabled state for managed children |

No measured usage, grant expiry, or generated execution state is imported into
the preference record.

## Broker interface and roles

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

## Screen-time model

`SetPreferences` cannot alter `parent_control_enabled`. Only
`SetParentControl` owns the child extension lifecycle and the account's
Malcontent `LimitType` and `DailyLimit`. The daily limit is an integer from 0
through 1440 minutes; zero is grant-only mode. App policy remains independent
of whether the daily limit is enabled.

The package installs the extension system-wide so every GNOME Shell discovers
it during startup, while the broker controls activation independently for each
child. Enabling from the disabled state enables the child extension through
GNOME Shell's supported `gnome-extensions` interface when a live Shell owns it
(and through durable offline settings otherwise), clears stale
`ActiveExtension`, applies the selected daily limit, and reapplies the complete
saved app blocklist. Changing the limit while already enabled preserves the
current grant. Disabling deactivates the extension, clears the daily restriction
and current grant, retains the configured choices, and reapplies the saved app
blocklist. These operations verify the resulting AccountsService and GNOME
configured and active extension state before committing the preference record
and restore the old state on failure. Live activation is accepted only when
GNOME Shell reports the extension both enabled and active; deactivation is
accepted only when it reports neither. Offline activation is verified against
the durable settings that Shell will consume at next login.

The broker owns the backend-compatible grant formula:

```text
ActiveExtension = max(Daily allowance remaining, One-time grant remaining)
                  + Additional one-time grant
```

For the Parent App, the administrator queries usage directly through the public
Malcontent parent interface, reads the current grant, computes the two remaining
operands, and asks `CalculateRemainingTime` to validate and apply the formula.
For a fixed-duration request, the broker launches the fixed-purpose
`oh-no-parent-control-query-usage` helper under the authenticated approver's UID
and primary GID. The helper opens a new system-bus connection and returns only
usage intervals; the root broker validates them and owns every write. A
rest-of-day request instead computes the seconds to the next local midnight with
timezone-aware epoch arithmetic.

The child extension uses GNOME Shell's supported time-limit manager and the
public Malcontent estimate signal/query for the daily estimate. It passes that
estimate to `CalculateOwnRemainingTime`; the broker derives the child from the
caller and reads the live `ActiveExtension` itself. The panel counts down in
minutes and then seconds, preserving its last verified estimate across a
temporary read failure.

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
administrator accounts bypass this child-only authentication check. Because its
login-time `RuntimeMaxSec` snapshot would terminate a live session after a
later grant, the PAM session helper clears that cap after `pam_systemd` creates
the scope; broker startup also attempts to clear stale caps on existing managed
sessions. Expiry therefore locks the child instead of logging out that child or
ending another user's foreground session. Expiry does not itself terminate
applications. On each new child session and each transition from locked to
unlocked, the child component invokes the broker-owned `PrepareOwnSession`
reconciliation described below; the unprivileged component neither decides
whether a grant is current nor signals processes itself.

## Application policy and enforcement

The parent selects policy by desktop ID, but enforcement uses the corresponding
native executable path, public Snap command path, or full Flatpak ref. The
broker discovers launchers from the selected child's user XDG directories
before system directories, so the catalog reflects that child's app grid. On
every app-policy save it resolves each still-present desktop ID again; a
self-updated executable is not replaced by a stale target, while a missing
app's saved rule remains intact. After
installing and verifying the complete policy, the broker stops applications
whose effective policy just became more restrictive. It stops only matching
processes owned by the selected child, across all of that child's retained
sessions. Policy saves serialize with approvals, revocations, and session
preparation so a concurrent grant cannot relax a newly saved hard block.

The live AccountsService `AppFilter` is always a blocklist. Its complete form
contains hard and soft targets. An approved request that allows soft blocked
apps omits only conditional targets; hard targets remain. A same-directory
basename pattern may accompany a native AppImage target. Conditional patterns
participate only while their owning conditional target is in the live blocklist.

Malcontent and GNOME enforce supported launcher, Snap command, and Flatpak
identities. To prevent a native target from bypassing the launcher policy
through a desktop file, file manager, or command, the broker mirrors live native
targets into
UID-scoped fapolicyd execute denials. Ordinary targets use exact paths. Since
fapolicyd 1.3 cannot quote whitespace safely, affected existing executable
names use their SHA-256 object identity. Pattern rules put exact safe-file
allowances before a denial for the guarded directory, so a matching new
AppImage is denied before a later rescan while unrelated existing executables
remain usable.

Every broker `AppFilter` write synchronously reconciles and reloads the
aggregate fapolicyd policy. The broker also subscribes to AccountsService
`PropertiesChanged` and rescans every 30 seconds so supported external changes
and new safe nonmatches are reconciled. Rule replacement is atomic; reload
failure restores and reloads the previous rule file. On startup, reconciliation
completes before the D-Bus object is registered.

The child session asks the broker to prepare application policy whenever a new
session becomes usable or a locked session resumes. `PrepareOwnSession` derives
the target child from the D-Bus caller and serializes with approval and
revocation. While holding that transaction lock, the broker re-reads the
authoritative `ActiveExtension`; the child component's earlier observation of
expiry is never used as authority.

If the recorded grant has expired, the broker obtains the canonical hard-and-
soft targets and patterns from saved preferences, preflights UID-scoped process
termination, restores and verifies the complete `AppFilter` and derived
fapolicyd policy, and then stops matching applications owned by that child
across all of the child's sessions. The remembered request-form toggle does not
extend an expired grant and is not consulted for this decision. A cleared grant
with no pending expiry reconciliation requires no additional transition.

If `ActiveExtension` is currently valid, session preparation is a no-op. This
includes a replacement grant approved after the previous grant expired but
before the child logs in or unlocks. The replacement approval has already
installed the policy selected for that grant: an approval allowing soft apps
therefore preserves the hard-only filter and every running application, while
an approval that keeps soft blocks has already restored the complete filter and
stopped blocked applications. Session preparation must not repeat or reverse
either successful approval transaction.

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

## Main flows

1. **Manage:** The Parent App selects one child, loads preferences, child-specific
   launchers, and time status, then serializes automatic saves in interaction
   order. App policy applies immediately, including stopping the selected
   child's newly blocked running applications in every retained session.
   Screen-time changes go through
   `SetParentControl`; revocation goes through `RevokeOneTimeGrant` after a
   confirmation that running blocked apps will close.
2. **Child session entry:** On extension startup and after an unlock transition,
   the child component calls `PrepareOwnSession`. The broker re-reads the grant
   under the shared transaction lock. It reconciles and terminates only for an
   expired grant; a current replacement grant returns without changing policy
   or processes.
3. **Child request:** Selecting the panel indicator launches the kiosk GTK form
   as a fullscreen overlay. `GetOwnAccount` fixes and collapses the child
   selector. The overlay loads shared per-child request choices, uses the
   child-only mute value, and calls `RequestOwnAccess`. Cancel or Escape closes
   the overlay; approval briefly confirms success and then closes it.
4. **Kiosk request:** The dedicated GNOME session lists eligible children and
   approvers, loads the selected child's request choices, and calls
   `RequestAccess`. The GNOME session is declared as a kiosk session, which
   disables every XDG autostart desktop file; its complete application set is
   instead the kiosk compositor, request station, and authentication agent
   declared by the session's systemd target. It remains request-only. Cancel or
   Escape returns to the sign-in screen, and approval does so after a brief
   confirmation.

The child overlay and kiosk deliberately use the same GTK request form and
validation. Only account selection, mute surface, broker request method, and
exit behavior differ.

## Startup, login, and update lifecycle

Broker construction first reconciles all current AccountsService filters into
fapolicyd. It then reasserts the packaged extension's activation for every
preference-enabled eligible child and attempts to clear stale live-session
runtime caps. Only after those steps does it register the D-Bus object. A
startup reconciliation or extension-activation failure prevents the service
from becoming ready.

The packaged fapolicyd drop-in keeps the daemon in systemd's `activating` state
until a root-owned canary execution is denied by the live kernel policy. The
display manager requires completed fapolicyd startup, so a managed graphical
login cannot begin while the daemon rebuilds its trust database. Readiness
failure therefore fails closed before the login manager starts.

The PAM account stack exempts systemd, the kiosk account, and administrators.
For other accounts, the public AccountsService `LimitType` helper skips
`pam_malcontent` only when the account is positively confirmed unrestricted;
unknown or malformed state continues through the enforcing module. The kiosk
account is additionally confined to the dedicated GNOME session.

APT stops the broker and runs the packaged, version-stepped migration framework
before newly installed readers can access
saved preferences. A migration-in-progress marker also prevents systemd from
starting the broker. See `Data-Migration.md` for the schema contract.

Package activation is selected from a generated digest manifest. Depending on
the installed file that changed, an update needs no action, a broker restart, a
new child/kiosk session, or a reboot at the PAM/display-manager boundary. See
`Package-Update.md` for the classification rules.

## Installed layout

```text
/usr/bin/oh-no-parent-control                         kiosk/overlay launcher
/usr/bin/oh-no-parent-control-parent                  parent launcher
/usr/libexec/oh-no-parent-control-broker              broker launcher
/usr/libexec/oh-no-parent-control-query-usage         approver-scoped read helper
/usr/libexec/oh-no-parent-control-migrate-state       saved-data migration runner
/usr/libexec/oh-no-parent-control-session-limit-check PAM limit-state gate
/usr/libexec/oh-no-parent-control-clear-session-runtime-max
/usr/libexec/oh-no-parent-control-login-check         kiosk PAM service gate
/usr/libexec/oh-no-parent-control-execution-policy-{ready,probe}
/usr/libexec/oh-no-parent-control-preserve-extension-state
/usr/libexec/oh-no-parent-control-uninstall            verified removal helper
/usr/libexec/oh-no-parent-control-{provision,package-activation}
/usr/lib/oh-no-parent-control/{broker,parent,kiosk,common}/
/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/
                                                       immutable extension payload
/etc/oh-no-parent-control/config.json                  private machine configuration
/var/lib/oh-no-parent-control/preferences/             authoritative child records
/var/log/oh-no-parent-control/<component>/             daily component logs
/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules   generated UID-scoped denies
/usr/lib/systemd/system/{fapolicyd,display-manager}.service.d/
                                                       boot readiness ordering
```

## Package removal lifecycle

Debian package removal stops the broker before changing enforcement so its
reconciliation loop cannot restore policy during the operation. While the
packaged code and dependencies are still available, the removal helper finds
the extant accounts named by securely owned preference records and disables the
product extension, clears `LimitType`, `DailyLimit`, `ActiveExtension`, and
`AppFilter`, verifies each result, and transactionally removes and reloads the
generated fapolicyd policy. It attempts every managed account before reporting
failure, and package removal stops if any final state cannot be verified.
A mode-`0600` transient snapshot records the exact derived values before the
first write. If `prerm` is aborted, `postinst abort-remove` restores and
verifies that snapshot before debhelper restarts the still-installed service.
The snapshot is removed after either a successful rollback or successful
package removal.

After dpkg removes the payload, `postrm` removes generated D-Bus and machine
configuration, the product's security-integration conffiles, transient package
markers, and the dedicated kiosk account only when a root-owned marker proves
that this package created the unchanged account identity. Installation can
reuse an existing reserved kiosk account after the provisioning checks reject
root or administrative identities, but it does not claim ownership of that
account, so later package removal preserves it. It reloads D-Bus and fapolicyd
after their policy files disappear. Canonical child preferences and
redacted product logs are deliberately retained for a later reinstall or
administrator-directed archival; neither can enforce policy without the
cleared derived state.

## Logging

The broker is the sole file-log writer. Logs are under
`/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log`, owned by
`root:sudo` so Ubuntu administrators can read them and other users cannot.
Parent, child, and kiosk records are forwarded over D-Bus after role checks;
broker records are written internally. A component's first event on a new day
prunes that component beyond the newest ten dated files.

## Design invariants

- One validated preference record exists per child; private policy is never
  stored in a user home.
- Preferences hold durable intent; AccountsService and fapolicyd hold derived
  enforcement state, and Malcontent owns measured use.
- All cross-account writes and all product authorization pass through the
  broker. A front end may perform only the documented identity-sensitive,
  read-only usage query directly.
- The broker resolves caller identity from system D-Bus and revalidates roles,
  targets, and stale request inputs before privileged writes.
- A temporary request may remove soft blocks only; it can never remove a hard
  block. The complete saved filter is the recovery state. Session-entry
  reconciliation acts only on an expired grant; a current replacement grant
  and the live filter installed by its approval take precedence.
- The kiosk remains request-only, the Parent App remains management and
  revocation only, and the child extension has no independent settings UI.
- The kiosk GTK request GUI is the single request form. The child session runs
  that form in overlay mode; changes must remain compatible with both surfaces.
