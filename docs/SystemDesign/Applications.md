# Application policy and enforcement

[System design overview](../System-Design.md)

The broker translates desktop choices into live AccountsService filters and
UID-scoped native execution rules. Implementation:
[catalog.py](../../broker/oh_no_parent_control/catalog.py),
[execution_policy.py](../../broker/oh_no_parent_control/execution_policy.py),
[app_termination.py](../../broker/oh_no_parent_control/app_termination.py),
[core.py](../../broker/oh_no_parent_control/core.py) and
[adapters.py](../../broker/oh_no_parent_control/adapters.py).

## Application policy and enforcement

Parents select policy by desktop ID; enforcement uses native executable paths,
public Snap commands or full Flatpak refs. Blocking is the union of targets:
an allowed entry cannot override another entry's block on a shared identity.
Hard blocks always apply; a temporary approval may omit soft targets.

Discovery reads the child's XDG directories before system directories. The first
desktop ID wins even when hidden or unlistable. Names and descriptions use the
calling parent's saved language and fall back to the untranslated OS entry.
Language changes do not alter launch targets.

Relative native commands resolve against an explicit absolute desktop `Path`,
then the child's `.local/bin` and `bin`; bare names finally use
`/usr/local/bin`, `/usr/bin`, `/bin`. Discovery never inherits the broker's
administrator PATH or evaluates shell profiles. Native targets are canonicalized
before generic-wrapper exclusion. The fixed AppImageLauncher wrapper resolves
only an existing absolute first-argument `.AppImage` payload that is not itself
a generic launcher. `TryExec` and unsupported layouts do not make a shared
wrapper an application identity.

Each save resolves current desktop IDs again and preserves missing applications'
saved rules. A disappeared ID's wildcard transfers to a new launcher only when
the exact-directory basename glob yields a unique association in both directions.
Conflicting current choices, precise overrides and ambiguous matches stay under
their original IDs. Equivalent duplicate choices may consolidate. Parent shows
an inherited choice and replaces the old ID on the next save; the broker repeats
the association at commit to handle intervening updates. This keeps the existing
preference format.

Parent caches each child's catalogue for the window's lifetime. Reopen Parent
to refresh added or removed launchers; switching children reuses cached lists.
Changing Parent's language also invalidates the cache. See the
[frontend catalogue lifecycle](Frontends.md#parent-controls-and-shared-information).

## Running application identity

After installing and verifying a more restrictive policy, the broker terminates
only matching processes owned by the selected child across their retained
sessions. The save delta comprises newly blocked targets/patterns and soft-to-hard
transitions. Restoring an already-saved soft block after an exception does not
itself add that app to the termination delta.

Native discovery matches direct executables and exact systemd-escaped desktop
application IDs in GNOME/unprefixed scopes and services under the child's
`app.slice`. It captures descendants before signalling, including Steam games
and AppImage payloads that move scopes. Parent start times reject reused PID
links. Every target is independently UID-verified and pinned with a pidfd; no
whole session, user slice or unrelated account is terminated. Snap security-label
and Flatpak instance matching remain separate supported identities.

Mounted AppImages can match through `APPIMAGE`/`APPDIR` only when the source
matches a blocked target/pattern, the kernel executable belongs to that exact
FUSE mount and its metadata identifies the child as owner. Environment values
alone never select an unrelated executable. Runtime identities are derived,
not preferences; diagnostics record counts rather than paths or environment.

## Live filter and execution rules

Broker-written AccountsService `AppFilter` values are blocklists. Complete policy
contains hard and soft targets; approvals including soft apps omit only conditional
targets and their associated wildcard guards. Malcontent/GNOME enforce supported
launcher, Snap and Flatpak identities. An external allowlist supplies no native
targets/patterns until it becomes a blocklist again.

For native bypass routes, fapolicyd mirrors live targets into UID-scoped execute
and open denials. Ordinary targets use exact canonical paths. Existing executables
whose paths contain whitespace or commas use SHA-256 identity; this also denies
identical bytes at other paths for that UID. A precise UI choice therefore need
not produce a path-only kernel clause. Open denials prevent interpreters or
AppImageLauncher from reading a blocked payload and executing a different object;
the selected child cannot read/copy those files. Other accounts remain unaffected.

Concrete denials appear in `01-oh-no-parent-control-deny.rules`, before
distribution trusted-file allows. Wildcard guards and exceptions remain in
`89-oh-no-parent-control.rules`, after distribution language/library restrictions.
Both files change, compile, notify and roll back together under one policy lock;
removal clears both. On an existing enforced administrator/distribution policy,
the early file contains no allowances. A trusted future wildcard match can still
bypass the late guard on that computer.

Fedora may instead use an owned original-permissive mode when the package
transaction proves fapolicyd was absent or an inactive, unmodified stock dependency.
A committed root-owned provenance receipt and matching original-permissive fallback
permit complete early wildcard groups before that fallback and trusted-file
allows. Invalid receipt ownership/schema/fallback identity refuses construction;
missing, uncommitted or preserved-policy receipts keep the ordinary deny-only
early layer. Administrator restrictions must precede those early exceptions and
fallback or replace the mode through guarded lifecycle handling. This is package
state, not a preference, and uses supported fapolicyd 1.3.6/2.0 rules.

### Wildcards and failure isolation

Patterns are absolute paths with `*` or `?` only in the basename, in the
native target's canonical directory. The editor expands a bare name only against
an unambiguous directory. Validation rejects directory whitespace and unsupported
rule characters. Recognized versioned AppImages suggest a stable application
prefix wildcard; saving that default is not a custom override. Existing saved
patterns are not silently rewritten.

A wildcard group places safe-file exceptions before its directory execute guard.
It also guards opens of ELF executables, shared libraries and bad-ELF objects,
covering new AppImages before a rescan while leaving ordinary documents readable.
Existing nonmatching regular files, including non-executable ELF files, receive
exact open exceptions. Existing immediate subdirectories receive prefix allowances;
new nonmatches require reconciliation.

Concrete blocks precede all exceptions; nested guards precede enclosing-directory
exceptions. Explicitly blocked executables need no allowance, even if their names
do not match the wildcard. No hash allowance is emitted, because identical bytes
at a matching filename must remain blocked.

A directory and its exceptions are indivisible. Inspection or representation
failure omits that entire UID/directory group; an unreadable/changing executable
requiring a hash omits only its concrete denial. An unrepresentable non-executable
nonmatch needs no exception only when a bounded no-follow read establishes
non-ELF content. Otherwise the wildcard group is omitted. Other groups/accounts
retain their rules. This deliberate partial-enforcement fallback can leave apps
or future versions unrestricted; it never installs a partial group or changes
the saved wildcard into a precise path.

Preferences and live filters remain intact and every rescan retries the original
rules. Local omissions do not prevent broker startup. Invalid account identity,
preference corruption, storage and compile/reload failures still fail with rollback.

The adapter publishes omitted-rule identities in memory only after successful
notification, including valid cache reuse. Role/target-checked `GetPolicyWarnings`
returns affected desktop IDs, or an empty ID for an unmatched live rule. Parent
shows a persistent notice, refreshes it after saves/polling and opens the ordinary
error report once per changed warning set. Automatic reports contain omission
counts, never app identities or paths.

Screen-time changes preflight aggregate rules with the proposed complete saved
blocklist. Fatal rendering failure leaves limits, grants, extension activation and
preferences untouched; isolated omissions retain their warning behavior.
Commit reconciles again because preflight cannot exclude later external changes.

### Notification recovery and acknowledgement limit

Every broker filter write synchronously reconciles aggregate rules. AccountsService
notifications and a 30-second rescan also refresh supported external changes and
safe nonmatches. Startup reconciles before registering D-Bus.

Replacement is atomic. Compilation uses `fagenrules`; notification uses
`fapolicyd-cli --reload-rules`, avoiding the trust refresh of `fagenrules --load`.
A successful-notification cache permits reuse only when disk bytes match this
adapter's recorded success. Reconciliation/removal invalidates it before changes.
Failed forward notification restores and reloads old content; failed rollback
leaves the record unknown. Restoring files alone never establishes success, and
a new adapter starts unknown.

Command completion and AccountsService readback do **not** acknowledge active
daemon policy. Asynchronous rejection/restart or external edits can invalidate
the cache's assumptions. The boot canary proves initial enforcement only.
A ruleset digest emitted before parsing, rule listings and performance statistics
cannot certify an active generation.

### Generation witness design gate

No production save, approval, reconciliation or removal uses a policy-generation
witness. Stronger acknowledgement remains unresolved: fresh rule-attributed
positive execution and a deny control must bind to compiled inputs and a daemon
invocation, reject stale/foreign decisions, partial parsing and permissive/stopped
enforcement, and cover rollback/removal. A marker or nonce denial alone is
insufficient: queue overflow can deny without rule evaluation, and logging can
precede permissive-mode response handling. A product marker also cannot certify
arbitrary administrator rules.

<a id="rule-decision-correlation-boundary"></a>
<a id="bounded-probe-transport-and-open-limits"></a>
<a id="settlement-after-permanent-sender-loss"></a>

### Pre-exec admission for a causal witness

Dormant support in `execution_probe.py`, `probe_channel.py`,
`probe_generation.py` and fixed native gate/witness payloads explores this boundary.
It is not connected to policy commits and never returns a policy receipt;
`executed` remains false even for positive native lifecycle diagnostics.

The adapter uses an owned single-use Unix D-Bus sender and a separate shared
read-only observer on the same bus. Only the sender creates/releases a fixed
transient probe unit against the captured unique systemd owner. A retained
asynchronous create reply distinguishes pending, replied, collision and uncertain
outcomes. Bounded local waits never imply remote cancellation or replay.
Pending ownership survives interruptions; collisions never authorize inspection
or mutation of another unit. The observer is never closed or used for mutation.

A private mode-0700 generation holds an exclusive mode-0500 witness copy with
pinned descriptors, inode/content identity and no writable descriptors. Before
admission, the lifecycle binds kernel peer credentials, exact unit/command,
root identity, original job reply, stable invocation, manager owner and effective
four-second job timeout. It consumes admission before its sole send. A selected
gate then pathname-execs that exact witness on the single connected endpoint.
No shell, arbitrary command, FD-exec bypass or broad policy allowance is exposed.

The fixed 40-byte versioned frame protocol rejects extra/truncated data, wrong
stage/invocation, ancillary descriptors and timeouts. Gate I/O shares a two-second
monotonic deadline; witness output has its own two-second deadline. Native frames
and matching terminal observations are diagnostics, not rule-decision attribution.

Recovery never admits again or promotes a failed attempt. Unit reference release
requires retained terminal evidence and create reply; generation collection waits
for unit settlement, client closure and channel cleanup. Permanent sender loss
settles only with the original successful reply/terminal evidence, unchanged
manager, absent sender and confirmed unit absence. Earlier loss, stuck processes,
uncompleted callbacks and manager replacement may remain unresolved.

The broker runtime directory is preserved on stop/restart and cleared at reboot.
Owners delete only recorded identities through retained descriptors; replacement,
hard links, unknown identity or incomplete settlement retain recovery coordinates.
Private ownership is not kernel sealing against hostile root. A restarted broker
cannot adopt or replay lost admission state. Selected native lifecycle, sandbox
and storage checks do not establish broker event-loop/restart recovery, live
replacement/PID-reuse resistance or full policy attribution.

## Session-entry reconciliation

`PrepareOwnSession` derives the child from bus credentials and serializes with
approval/revocation. Under that lock it re-reads authoritative `ActiveExtension`:

| Grant state | Effect |
| --- | --- |
| Nonzero and expired | Restore/verify complete saved hard and soft filters and native rules, then terminate matching child-owned apps across retained sessions. |
| Current, including a replacement approval | Preserve current policy and running apps. |
| Zero duration | No transition. |

The request form's remembered soft-app choice is not authority. An expired
nonzero record is not cleared, so later calls may repeat reconciliation.
There is no expiry worker that immediately rewrites policy: periodic native
reconciliation mirrors the live filter. While daily time remains, natural grant
expiry alone neither locks the desktop nor restores omitted soft blocks.

## Policy boundaries

App saves install complete saved policy even during a soft-app exception and
serialize with approval, revocation and session preparation. Preferences precede
filter reconciliation so rendering sees new patterns. Before termination,
failure restores old preferences/filter; after termination begins, stricter
requested policy remains and failure is reported.

Native enforcement covers rendered paths, hashes and directories; it does not
cover every copied/renamed binary, interpreter, shared wrapper or alternate route.
The [threat model](../Threat-Model.md) retains separate security targets.

## Related design

- [Broker transactions](Broker.md#authorization-and-grant-transactions): approval, revocation and irreversible failures.
- [State](State.md): saved targets and patterns.
- [Screen time](Screen-Time.md#countdown-and-expiry-enforcement): exhaustion and locking.
- [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle): boot readiness.
