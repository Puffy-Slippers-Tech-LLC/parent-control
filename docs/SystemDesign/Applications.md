# Application policy and enforcement

[System design overview](../System-Design.md)

Read this for desktop discovery, native/Snap/Flatpak identities, execution
rules, running-app termination, or grant-expiry reconciliation.

Implementation: [catalog.py](../../broker/oh_no_parent_control/catalog.py), [execution_policy.py](../../broker/oh_no_parent_control/execution_policy.py), [app_termination.py](../../broker/oh_no_parent_control/app_termination.py), [core.py](../../broker/oh_no_parent_control/core.py), [adapters.py](../../broker/oh_no_parent_control/adapters.py).

## Application policy and enforcement

The parent selects policy by desktop ID, but enforcement uses the corresponding
native executable path, public Snap command path, or full Flatpak ref. The
broker discovers launchers from the selected child's user XDG directories
before system directories, so the catalog reflects that child's app grid. The
first file for each desktop ID takes precedence even if it is hidden or cannot
be listed; a lower-priority launcher does not replace that child's override.
Relative native commands use an explicit absolute desktop `Path`, when present,
then the selected child's `.local/bin` and `bin`. Bare command names fall back
to `/usr/local/bin`, `/usr/bin`, and `/bin`, in that order, without inheriting
the broker's administrator `PATH` or current directory. Native targets are
canonicalized before generic-wrapper exclusion. This fixed discovery policy
does not evaluate account shell profiles or arbitrary session PATH changes.
On every app-policy save it resolves each still-present desktop ID again; a
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
policy. The renderer skips replacement and reload only when the disk contents
match a successful notification recorded by this adapter instance. The broker uses
the public rules-only reload interface: it compiles with `fagenrules` and
notifies with `fapolicyd-cli --reload-rules`, avoiding the trust-database refresh
triggered by `fagenrules --load` (SIGHUP). Command success alone does not
acknowledge daemon activation; installed transition qualification and an active
policy acknowledgement remain Task 15A work. The broker subscribes
to AccountsService
`PropertiesChanged` and rescans every 30 seconds so supported external changes
and new safe nonmatches are reconciled. Rule replacement is atomic; reload
failure restores and reloads the previous rule file. On startup, reconciliation
completes before the D-Bus object is registered. An external AccountsService
allowlist is not converted into native denials: the adapter supplies no targets
or patterns for that account until it has a blocklist again.

### Notification recovery and acknowledgement limit

`FapolicydPolicy.reconcile` and `remove` invalidate the in-memory notification
record before changing rules. A successful compile/notification records the
candidate, or the previous contents after successful rollback. Failed rollback
leaves the record unknown: restoring the source file alone must not let a later
identical reconciliation return success without retrying compilation and
notification. A new adapter also starts unknown, so broker restart does not
inherit an unverified disk-only success. All updates remain under the existing
policy lock; rollback logs contain operation and exception type only.

This record establishes command completion, **not active daemon policy**.
Successful notification followed by asynchronous daemon rejection/restart or
external rule changes is not detected by this cache. Generation-specific bounded
acknowledgement, including rollback, remains [Task 15A work](../TestAutomation/Task-15.md#task-15a-continuation--2026-09-08).
The boot canary proves initial enforcement only. The existing public
[`--reload-rules` contract](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/doc/fapolicyd-cli.8)
describes notification; disk rule listings and performance statistics cannot
be assumed to acknowledge a requested generation.

The [activation interface audit](../TestAutomation/Evidence/15A-Activation-Interface-Audit-20260911.md)
also rejects the journal's ruleset digest as an activation receipt: released
v1.4.5 `open_file` emits it before `_load_rules` parses the file. Its public
status report has no requested-generation receipt. These are audited upstream
facts, not qualification of the guest's installed version. That version could
not be recovered from the historical artifact path in this slice.
`tests/integration/system_enforcement.py::record_execution_backend` now records
validated package version and installed executable digest through the existing
native-case evidence callback. Local regressions in
`tests/unit/test_system_enforcement.py` cover refusal and partial-evidence
boundaries; the added capture has not run in the guest. It does not identify
active daemon rules. The next witness design must distinguish stale rules and
absent/permissive enforcement, bound its operations, and acknowledge rollback
and removal; a single allow/deny canary is insufficient.

[Local recovery evidence](../TestAutomation/Evidence/15A-Notification-Recovery-20260911.md)
retains failing-before/passing-after checks in
`tests/unit/test_execution_policy.py`: separate disk/compiled/daemon doubles,
failed forward and rollback notifications for reconciliation/removal, repeated
failure, eventual recovery, new-adapter recovery and successful-rollback reuse.
This increment is locally tested, not installed-qualified. It uses the existing
`process-restart` activation class and changes no persistent schema. Downstream
policy-save, grant/session and removal transactions reuse this adapter; the
[rules-only live evidence](../TestAutomation/Evidence/15A-Rules-Only-Reload-20260908.md)
retains its original scope and does not qualify this new recovery behavior.

### Generation witness design gate

The [kernel-witness audit](../TestAutomation/Evidence/15A-Kernel-Witness-Audit-20260911.md)
adds two concrete constraints: upstream v1.4.5 reload ignores the parser's
failure return, and queue overflow can produce a denial without evaluating
any rule. A marker before product rules, or a nonce denial with an adjacent
allowance, therefore cannot acknowledge the requested policy. These findings
are source analysis, not installed qualification.

The candidate is a fresh generation's positive rule-decision receipt plus
actual execution, paired with a rule-attributed deny control. Bind both to
the compiled inputs and daemon invocation; reject stale/foreign decisions,
partial parsing, missing records, permissive/stopped enforcement and identity
changes. The linked audit records the acceptance matrix and remaining proof
obligations. This protocol is not yet implemented or established sufficient;
in particular, a product marker cannot certify arbitrary administrator rules.

Reuse the broker's Gio system-bus transport for a narrowly scoped systemd
transient probe service with explicit startup/runtime/stop deadlines. The
[bounded transport](#bounded-probe-transport-and-open-limits) now has local
refusal coverage; installed qualification and complete ambiguous-create recovery
remain pending. `subprocess` timeouts do not bound initial process creation,
and the boot/terminal helpers cannot supply an owned handle while exec is
stalled there. Do not infer ownership from a unit name or interpret generic
exec failure as a policy decision.

Rollback requires a fresh receipt for restored content. Reversible removal
needs a witness that survives deletion of the account-policy file; any separate
witness must ship its `postrm` deletion and baseline/empty-directory handling
together. See the [removal limitation](Package-Removal.md#execution-policy-baseline).
No generated witness files, persistent schema or policy activation behavior
have been added. Current notifications and their cache remain weaker than
acknowledgement.

### Bounded probe transport and open limits

`execution_probe.ExecutionProbe.run` reuses `adapters._call` on an existing
Gio system-bus connection. It is dormant: no broker transaction invokes it.
It executes only the existing packaged canary, with a fresh random unit name,
`Type=exec`, finite start/runtime/stop/job limits, no restart and null standard
streams. Calls target the captured unique systemd bus owner and have finite
deadlines. The immutable result retains manager, unit, job when returned,
observed invocation, terminal status and separate reference/cleanup outcomes.
Broker payload activation is `process-restart`; the boot canary and its gate
are unchanged, and there is no saved-data migration.

Systemd's `AddRef` retains fast-exit evidence for the sending bus client;
`UnrefUnit` releases only that client's reference. `CollectMode=inactive-or-failed`
permits subsequent collection. The adapter never stops, kills, resets or
restarts a unit. Identity-bracketed reads reject replacement; ordinary state
transitions are observed again. Success requires terminal evidence followed
by confirmed collection. Exit 203 is an execution failure, never a deny receipt.

The [transport evidence](../TestAutomation/Evidence/15A-Bounded-Probe-Transport-20260911.md)
links the public systemd interfaces/source and
`tests/unit/test_execution_probe_cleanup_safety.py` regression matrix. This is
**local double coverage, not live qualification or a generation receipt**.
A lost create reply always fails; when its unit is observed terminal, evidence
and collection can still be retained. `ExecutionProbe.pending` now retains the
immutable recovery result before dispatch and through interrupted cleanup.
Keep one adapter for the connection lifetime: its nonblocking operation lock
refuses overlapping run/recovery calls, and an unsettled attempt refuses another
create. `recover()` uses the original manager, name, description and observed
invocation to collect a late unit without replaying creation. Each recovery has
separate finite observation/release deadlines. It preserves the original failure;
recovering a successful execution's failed cleanup returns `recovered-cleanup`,
never a successful probe receipt. These guarantees are per retained adapter;
there is no connection-wide registry or broker recovery scheduler yet.

`UnrefUnit` replies `NoSuchUnit`/`NotReferenced` permit checking collection after
a lost release reply. `reference_released` describes the latest release check,
not proof that delayed creation cannot add a future reference. Only terminal
evidence followed by absence clears `pending`. The
[recovery evidence](../TestAutomation/Evidence/15A-Probe-Recovery-20260911.md)
records the corrected public error name, delayed dispatch, interrupted release,
concurrency and non-promotion regressions in the same cleanup-safety module.
This remains **local double coverage only**.

Absence before terminal observation cannot exclude delayed dispatch. Persistent
absence, manager loss or a stuck task leaves cleanup uncertain; retain the
adapter and recovery coordinates rather than automatically retrying creation.
An indefinitely delayed request on a long-lived connection is still unresolved:
recovery handles its eventual appearance but cannot guarantee a finite final
settlement. The linked source audit identifies dedicated-client disconnection
as the next lifetime candidate, not an implemented or qualified solution. Resolve
that boundary and bounded connection cleanup before live use.
The adapter does not yet provide fresh executable paths, decision records,
compiled-input/daemon binding or forward/rollback/removal acknowledgement.
External privileged mutation before the first invocation observation is not
qualified as original-job evidence; downstream receipts must resolve that
binding too. All 15A/15B, grant/session and removal consumers retain these limits.

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
