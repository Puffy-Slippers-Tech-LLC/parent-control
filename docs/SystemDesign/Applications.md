# Application policy and enforcement

[System design overview](../System-Design.md)

Read this for desktop discovery, native/Snap/Flatpak identities, execution
rules, running-app termination, or grant-expiry reconciliation.

Implementation: [catalog.py](../../broker/oh_no_parent_control/catalog.py), [execution_policy.py](../../broker/oh_no_parent_control/execution_policy.py), [app_termination.py](../../broker/oh_no_parent_control/app_termination.py), [core.py](../../broker/oh_no_parent_control/core.py), [adapters.py](../../broker/oh_no_parent_control/adapters.py).

## Application policy and enforcement

The parent selects policy by desktop ID, but enforcement uses the corresponding
native executable path, public Snap command path, or full Flatpak ref. The
broker discovers launchers from the selected child's user XDG directories
before system directories, so the catalog reflects that child's app grid. On
every app-policy save it resolves each still-present desktop ID again; a
self-updated executable is not replaced by a stale target, while a missing
app's saved rule remains intact. After installing and verifying the complete
policy, the broker stops applications
whose effective policy just became more restrictive. It stops only matching
processes owned by the selected child, across all of that child's retained
sessions. Policy saves serialize with approvals, revocations, and session
preparation so a concurrent grant cannot relax a newly saved hard block.

## Running application identity

For native launchers, process discovery also resolves blocked targets and
patterns back to the child's current desktop catalog. It matches the exact,
systemd-escaped application ID in GNOME/unprefixed desktop application scopes
and services under that child's user manager's `app.slice`. This follows
launchers such as Steam and AppImages whose running executable differs from
the launch target. Every selected process is still independently UID-verified
and pinned with a pidfd; no entire session or user slice is terminated.
Discovery records child-owned descendants before any signal, including payloads
that move to a different application scope (such as an Electron AppImage) and
games launched by Steam. Parent start times reject stale links to reused PIDs.
Unrelated application scopes and other accounts remain outside this selection.
Mounted AppImage payloads also match through the documented `APPIMAGE` and
`APPDIR` runtime values when the source matches a blocked target or saved
pattern. The kernel-reported executable must be inside that exact FUSE mount,
whose mount metadata must identify the selected child as owner. This recovers
payloads after a self-update replaces the desktop ID or Electron moves to a
generic Chromium scope. Inherited environment alone does not select an
unrelated executable; the existing verified descendant traversal includes
games launched by the matched payload. Discovery logs report match counts,
never environment contents or application paths.
Direct executable, Snap security-label, and Flatpak instance matching continue
to apply. These runtime identities are derived; they are not stored in preferences.

## Live filter and execution rules

Broker-written AccountsService `AppFilter` values are blocklists. The complete form
contains hard and soft targets. An approved request that allows soft blocked
apps omits only conditional targets; hard targets remain. A same-directory
basename pattern may accompany a native AppImage target. Conditional patterns
participate only while their owning conditional target is in the live blocklist.

Malcontent and GNOME enforce supported launcher, Snap command, and Flatpak
identities. To prevent a native target from bypassing the launcher policy
through a desktop file, file manager, or command, the broker mirrors live native
targets into UID-scoped fapolicyd execute denials. Ordinary targets use exact
paths. The rule renderer uses SHA-256 object identity for existing executable
paths containing whitespace or commas, which its path-rule format cannot
represent safely. Pattern rules put exact safe-file allowances before a denial
for the guarded directory, so a matching new
AppImage is denied before a later rescan while unrelated existing executables
remain usable.

Every broker `AppFilter` write synchronously reconciles the aggregate fapolicyd
policy. The renderer replaces and reloads the rule file only when its contents
change; identical contents return without a reload. The broker also subscribes
to AccountsService
`PropertiesChanged` and rescans every 30 seconds so supported external changes
and new safe nonmatches are reconciled. Rule replacement is atomic; reload
failure restores and reloads the previous rule file. On startup, reconciliation
completes before the D-Bus object is registered. An external AccountsService
allowlist is not converted into native denials: the adapter supplies no targets
or patterns for that account until it has a blocklist again.

## Session-entry reconciliation

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
extend an expired grant and is not consulted for this decision. A grant with
zero duration returns without a transition. Reconciliation does
not clear an expired nonzero grant, so later session-entry calls may repeat
the strict-policy reconciliation until that grant is replaced or cleared.

If `ActiveExtension` is currently valid, session preparation is a no-op. This
includes a replacement grant approved after the previous grant expired but
before the child logs in or unlocks. The replacement approval has already
installed the policy selected for that grant: an approval allowing soft apps
therefore preserves the hard-only filter and every running application, while
an approval that keeps soft blocks has already restored the complete filter and
stopped blocked applications. Session preparation must not repeat or reverse
either successful approval transaction.

## Policy boundaries

App-policy saves install the complete saved blocklist even when a live grant
previously allowed soft apps. They terminate targets/patterns that become newly
blocked or move from soft to hard; a save does not terminate every already
blocked application. Preferences are saved before filter reconciliation so the
renderer sees the new patterns. Failures before termination restore old
preferences and filter; once termination starts, the requested strict policy
is retained and failure is reported.

Native enforcement covers the rendered paths, hashes, and guarded directories.
It is not a claim that every copied or renamed executable, interpreter, shared
wrapper, or alternate launch route is covered. The [threat model](../Threat-Model.md)
separately records security requirements and evidence still needed; its target
requirements must not be presented as implemented guarantees.

## Related design

- For approval/revocation ordering and irreversible failure handling, read [Broker](Broker.md#authorization-and-grant-transactions).
- For saved targets and patterns, read [State](State.md).
- For time exhaustion and session locking, read [Screen time](Screen-Time.md#countdown-and-expiry-enforcement).
- For boot readiness, read [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle).
