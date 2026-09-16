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

Customer E2E follows the [surface-only contract](../TestAutomation/E2E-Building-Blocks.md).
Internal policy qualification remains separate from customer acceptance.

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
acknowledge daemon activation; installed transition qualification is separate
from the deferred active-policy acknowledgement design.
The broker subscribes
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
acknowledgement, including rollback, remains separate product-design work.
The boot canary proves initial enforcement only. The existing public
[`--reload-rules` contract](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/doc/fapolicyd-cli.8)
describes notification; disk rule listings and performance statistics cannot
be assumed to acknowledge a requested generation.

The activation interface audit
also rejects the journal's ruleset digest as an activation receipt: released
v1.4.5 `open_file` emits it before `_load_rules` parses the file. Its public
status report has no requested-generation receipt. These are audited upstream
facts, not qualification of the guest's installed version. That version could
not be recovered from the historical artifact path in this slice.
`tests/integration/system_enforcement.py::record_execution_backend` now records
validated package version and installed executable digest through the existing
native-case evidence callback. Local regressions in
`tests/unit/test_system_enforcement.py` cover refusal and partial-evidence
boundaries; the installed native lifecycle and sender-loss qualifications below
now retain this capture. It does not identify
active daemon rules. The next witness design must distinguish stale rules and
absent/permissive enforcement, bound its operations, and acknowledge rollback
and removal; a single allow/deny canary is insufficient.

Local recovery evidence
retains failing-before/passing-after checks in
`tests/unit/test_execution_policy.py`: separate disk/compiled/daemon doubles,
failed forward and rollback notifications for reconciliation/removal, repeated
failure, eventual recovery, new-adapter recovery and successful-rollback reuse.
This increment is locally tested, not installed-qualified. It uses the existing
`process-restart` activation class and changes no persistent schema. Downstream
policy-save, grant/session and removal transactions reuse this adapter; the
rules-only live evidence
retains its original scope and does not qualify this new recovery behavior.

### Generation witness design gate

The kernel-witness audit
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
[bounded transport](#bounded-probe-transport-and-open-limits) has local refusal
coverage and selected installed native lifecycle/sandbox qualification below;
complete ambiguous-create recovery remains pending. `subprocess` timeouts do not bound initial process creation,
and the boot/terminal helpers cannot supply an owned handle while exec is
stalled there. Do not infer ownership from a unit name or interpret generic
exec failure as a policy decision.

Rollback requires a fresh receipt for restored content. Reversible removal
needs a witness that survives deletion of the account-policy file; any separate
witness must ship its `postrm` deletion and baseline/empty-directory handling
together. See the [removal limitation](Package-Removal.md#execution-policy-baseline).
No policy-generation witness rules, persistent schema or policy activation behavior
have been added. Current notifications and their cache remain weaker than
acknowledgement.

### Rule-decision correlation boundary

The installed qualification captured fapolicyd `1.3.6-1`; the corresponding
upstream [v1.3.6 policy implementation](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.3.6/src/library/policy.c)
and [message transport](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.3.6/src/library/message.c)
provide a candidate decision source: `allow_syslog`/`deny_syslog` records through
syslog. The public [configuration format](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.3.6/doc/fapolicyd.conf.5)
supports `rule,dec,perm,pid,uid,:,path`, within a 512-byte message limit.
The rule number is the one-based parsed-rule ordinal, not a physical source
line. The daemon logs before applying permissive mode to the kernel response;
a logged denial therefore still requires an independently observed denied exec.
This is an upstream source audit, not qualification of distribution patches or
the guest's effective logging configuration.

[`system_probe_decision.bind_positive_decision`](../../tests/integration/system_probe_decision.py)
is a pure test-only validator, with local regressions in
[`test_system_probe_decision.py`](../../tests/unit/test_system_probe_decision.py).
It joins the native `ProbeResult`'s admitted peer PID, invocation and fresh
generation path to an exact positive rule and decision record. It requires
settled native success, unchanged captured compiled/config bytes and backend
identity, active service state, explicit nonpermissive configuration and no
legacy `fapolicyd.rules` (which upstream prefers over `compiled.rules`). Its
small fixture grammar refuses unsupported syntax, sets, duplicate/missing
markers and malformed trailing rules. It does not implement the general daemon
parser. Production activation and its notification cache remain unchanged;
this test-only addition has activation class `none` and no saved-data change.

Use independently collected local journal entries. Per the
[trusted journal fields contract](https://github.com/systemd/systemd/blob/v259/man/systemd.journal-fields.xml),
the validator requires the daemon's boot, trusted invocation, PID, UID,
executable, unit and syslog transport. User-supplied `SYSLOG_PID`, identifier or
`INVOCATION_ID` cannot establish origin. The message PID is the admitted probe;
the journal `_PID` is the daemon. Missing/repeated/binary fields, truncated
messages, foreign paths/rules and out-of-window reception timestamps refuse.
Errors contain fixed reasons only. Raw records and correlation coordinates
belong in private test evidence, not product logs or operator summaries.

**Remaining limits:** the returned `PositiveDecision` is a correlated observation,
never an activation receipt. No live collector or rule writer is connected yet.
The collector must retain cursor ordering, detect duplicate candidate records,
bound collection and bracket the actual daemon and pinned input reads. Journal
timestamps measure reception, not exec. Equal endpoint snapshots cannot exclude
an intervening writer changing and restoring inputs; source configuration alone
does not prove effective daemon mode. A product marker cannot prove arbitrary
administrator rules parsed completely. Installed logging, a rule-attributed
deny control with native outcome, writer exclusion/detection, full-input binding,
rollback/removal and broker integration remain open. Reuse the native collector
for the first guarded fixture; do not treat these synthetic regressions as live
qualification.

### Bounded probe transport and open limits

`execution_probe.ExecutionProbe.run` reuses `adapters._call` with an existing
Gio connection as its read-only observer and a fresh owned `ProbeBusClient` as
its sender. It is dormant: no broker transaction invokes it.
The public `Gio.dbus_address_get_for_bus_sync(SYSTEM)` resolver obtains the
configured system-bus address; the client retains its single Unix transport
guard. Before manager lookup or creation, `GetId` on both connections must
identify the same bus. Only the owned sender issues `StartTransientUnit` and
`UnrefUnit`; a missing sender never falls back to the observer. The shared
observer is never disconnected by the adapter.
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
restarts a unit. Identity-bracketed reads reject observed replacement; ordinary
state transitions are observed again. Pre-observation replacement remains
unbound, so matching exits now return `identity-unproven`, never successful
execution. A future success also requires original-invocation evidence,
confirmed collection and completed owned-client closure. `client_closed`
records that separate lifecycle result. Exit 203 is an execution failure,
never a deny receipt.

The transport evidence
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
a lost release reply. Release is attempted only after terminal evidence has
been copied; absence or an observation deadline never authorizes dropping the
pin. `reference_released` describes that release check. After dispatch,
only terminal evidence followed by absence and completed client closure clears
`pending`. Before dispatch, client closure suffices. The
recovery evidence
records the corrected public error name, delayed dispatch, interrupted release,
concurrency and non-promotion regressions in the same cleanup-safety module.
This remains **local double coverage only**.

The evidence-retention correction
supersedes the earlier recovery qualification for late exit, failed property
reads and creation between the final absence read and release. `_release`
previously dropped the reference even without terminal evidence, allowing GC
to discard the result before recovery despite an open sender. It now retains
that pin in initial and repeated recovery calls until terminal evidence is
copied. Five failing-before/passing-after cases in
`tests/unit/test_execution_probe_cleanup_safety.py` cover these timings and
preserve the original failure after cleanup. Identity refusal and a stuck
process retain pending ownership, not a false cleanup result. This is locally
verified for these fault timings; the installed native lifecycle below qualifies
ordinary success and withheld-admission recovery, not these late-dispatch faults.

Absence before terminal observation cannot exclude delayed dispatch. Persistent
absence, manager loss or a stuck task leaves cleanup uncertain; retain the
adapter and recovery coordinates rather than automatically retrying creation.
An indefinitely delayed request on a long-lived connection is still unresolved:
recovery handles its eventual appearance but cannot guarantee a finite final
settlement. The linked source audit identifies dedicated-client disconnection
as the lifetime candidate. `execution_probe.ProbeBusClient` implements its
connection lifecycle, using public asynchronous Gio creation/closure,
a private GLib context, cancellation and finite observation deadlines. It
accepts one trusted Unix bus address, rejecting remote/fallback/autolaunch
transports. It never takes ownership of a supplied shared connection. Its
single-use, nonblocking operation guard retains an unfinished callback and any
late-created connection for subsequent `close()` calls; cancellation or a local
closed flag alone cannot retire a pending callback. A failed or interrupted open
cannot expose a usable connection. Close failure retains the same owned client.
No broker default-context callbacks are dispatched by these waits.

The client-lifecycle evidence
records local late-completion/interruption/refusal regressions in
`tests/unit/test_probe_bus_client_cleanup_safety.py` and real private-bus
creation, separate sender identity, observer survival, connection refusal and
stalled-authentication cancellation/EOF in
`tests/component/test_probe_bus_client.py`. This qualifies the Gio lifecycle on
the development host, **not systemd dispatch/reference or installed execution**.
The integration evidence
records the lifecycle's integration into `ExecutionProbe`: retain the adapter
through pre-dispatch open failure, interrupted/failed closure and ambiguous
dispatch. Unit collection is retained separately so close-only recovery does
not resnapshot a collected unit or promote the original failure. Settled runs
use fresh senders. Local integration regressions extend
`tests/unit/test_execution_probe_cleanup_safety.py`; the component module above
also qualifies the real resolver, failed pre-dispatch cleanup, sender
disappearance and observer survival, including a different private bus.
These are **local lifecycle/transport checks, not systemd qualification**.

An ambiguous dispatch retains the sending client so recovery can release any
late reference through its original owner after copying terminal evidence.
The linked correction's v259 source audit distinguishes failure to establish a
reference before job queueing from sender loss after reference establishment;
the latter queues GC without cancelling a job. Sender absence alone is not a
manager-dispatch barrier. Automatic disconnection in that
state remains deliberately unimplemented: removing the sender can also lose
retained terminal evidence, and client closure cannot prove manager dispatch
settlement. A permanently uncompleted callback remains an explicit unresolved
resource, with bounded waits rather than a false cleanup result.

The next transport step preserves the creation reply instead of deliberately
disconnecting to settle dispatch. `ProbeBusClient.start_create/poll_create` now
extend the same owned client with one asynchronous fixed-canary request on its
private context. The supported Gio no-timeout setting retains the callback;
each poll has a finite local deadline and does not cancel delivery. A pending
callback refuses `close()` without disarming the sender. The immutable
`ProbeCreateReply` retains the returned job or a role-neutral collision/uncertain
outcome; raw errors are neither retained nor logged. A never-completed request
remains pending, not finite guaranteed cleanup. `ExecutionProbe.run` now submits
through this retained route, and `recover` polls only that original callback.
`ProbeResult.create_outcome` records `not-submitted`, `pending`, `replied`,
`collision` or `uncertain` separately from terminal evidence and the overall
attempt outcome. A collected job is copied before reference release. Recovery
preserves the original failure when a reply arrives late; it never replays
creation or promotes that attempt to success.

The retained-reply evidence
qualifies late success/error replies and sender survival on a real private bus,
plus interrupted dispatch/polling, concurrency refusal and default-context
isolation with local doubles. Regressions extend the existing
`test_probe_bus_client_cleanup_safety.py` and `test_probe_bus_client.py` modules.
No systemd dispatch, reference lifetime or installed result is qualified by a
fake manager's reply. The integration contract is:

| Dispatch observation | Retained evidence and cleanup requirement |
| --- | --- |
| No request submitted | Existing owned-client lifecycle cleanup suffices. |
| Reply pending, including after a local deadline/interruption | Retain callback, sender, manager/unit/description coordinates and any terminal evidence; no replay, cancellation, reference release or disconnect. Poll the same call during recovery. |
| Job reply collected | Copy the original job before release. Require the existing terminal evidence, reference release, collection and client closure gates. A late reply never promotes a failed attempt. |
| Explicit `UnitExists` collision | Preserve the collision result; do not inspect or mutate the colliding unit. Close only the owned client. |
| Other error or transport loss | Preserve uncertain failure and existing evidence/recovery coordinates. Callback completion is not proof of no partial creation; no absence-only cleanup or success promotion. |
| Sender disappears unexpectedly | Its pin may be lost. Do not infer dispatch cancellation, retained evidence or process termination; report unresolved cleanup when those cannot be proven. |

### Settlement after permanent sender loss

`ExecutionProbe._collect_after_sender_loss` handles the narrower case where
the original successful creation reply and terminal snapshot were copied before
the owned sender disappeared. `_release` first requires terminal evidence and
a collected reply; a closed connection then takes a read-only settlement path.
It requires a successful creation reply, the original unique manager still
owning the service name, the original sender's unique name absent, and `NoSuchUnit`
from that captured manager. Only this conjunction permits reference/collection
settlement, followed by the existing channel/client/generation cleanup gates.
No observer mutation, reconnect, replay or process signal is introduced.
The original outcome and `executed=False` refusal remain unchanged.

The public [D-Bus name-owner contract](https://dbus.freedesktop.org/doc/dbus-specification.html#bus-messages-name-has-owner)
and [Gio closed-connection state](https://docs.gtk.org/gio/method.DBusConnection.is_closed.html)
supply the observations; neither observation alone proves systemd collection.
Bounded failure retains the same adapter and exact witness. Lost terminal
evidence, uncertain/pending creation, a retained unit, manager replacement and
unavailable reads still cannot settle. In particular, a native success frame
without terminal evidence does not authorize filesystem collection.

`test_native_closed_sender_settles_only_with_retained_evidence` reproduced the
missing cleanup path and now covers settlement and five refusal/recovery faults;
`test_native_sender_loss_before_terminal_retains_uncertainty` covers earlier loss.
The private-bus test
`test_installed_sender_loss_fault_retains_closed_identity_and_observer` qualifies
the test-only `system_enforcement._lose_probe_sender` fault using the original
client's bounded asynchronous close and callback owner. Safety regressions cover
late/interrupted closure and retry. The installed
`test_native_probe_permanent_sender_loss` selects loss only after complete native
terminal evidence, then fresh independent success. Its first guarded qualification
passed on systemd `259.5-0ubuntu3.4` in
`/tmp/onpc-system-lejxzgpd/evidence/result.json` and sibling
`../guest-results/enforcement.xml`: all five required executions passed, with no
failures/skips. Both stages retained native/terminal evidence, the fault stage
confirmed sender loss, and both collected their generation with effective
4,000,000 µs job timeout. Outer collection, cleanup and full restored-baseline
byte verification passed. This qualifies the terminal-evidence loss path;
pre-terminal loss refusal remains local evidence, not guaranteed finite
settlement. This changes
the existing broker module (`process-restart` activation), adds no system
integration or saved-data format, and leaves policy callers unchanged.

The reply-integration evidence
qualifies these run/recovery gates locally: pending success/collision replies,
interrupted polling, late job copying, outcome non-promotion and separate
terminal/reference/client settlement. A real private-bus collision also proves
that `ExecutionProbe` drives the retained callback and closes only its owned
sender while leaving the observer alive. The fake manager launches no unit;
installed dispatch/reference settlement is qualified separately by the native
lifecycle below, without extending that pass to every retained-reply fault.
Client closure after a collected reply still requires the unit-settlement gate.
The job-identity audit and refusal regressions
supersede earlier positive snapshot qualification. Systemd can merge a restart
and rerun the existing job ID; even a running/start job bracket cannot certify
the first invocation. A restart can overwrite invocation/status before the
first property read without changing name, description or command. The public
job result lacks invocation identity, and `RefuseManualStart` also refuses the
initial direct transient start. No job-polling binding was added.
`ExecutionProbe._snapshot` now returns `identity-unproven` for every otherwise
matching positive exit; current `run/recover` cannot return `executed=True`.
Terminal evidence still permits non-signaling release of only the owned sender's
reference and collection, not certification of the first invocation. Existing
uncertain-dispatch and replacement-retention gates remain in force.
The regression `test_original_job_cannot_certify_a_preobserved_replacement`
covers pre-read replacement and same-job rerun; both reproduced false success
before the correction. This is local refusal coverage, not positive binding.
The selected next implementation is the
[pre-exec admission contract](#pre-exec-admission-for-a-causal-witness), integrated
with the generation-witness gate, before real success/failure/cleanup
qualification. Signal subscription alone does not establish lossless
first-invocation evidence. Stuck processes and
permanent transport loss still cannot promise finite cleanup.
Do not close the broker's shared bus or replay creation.
The adapter does not yet provide fresh executable paths, decision records,
compiled-input/daemon binding or forward/rollback/removal acknowledgement.
External privileged mutation before the first invocation observation is not
qualified as original-job evidence; downstream receipts must resolve that
binding too. All enforcement, grant/session and removal consumers retain these limits.

### Pre-exec admission for a causal witness

**Native admission lifecycle now has installed success/refusal/fresh-success
qualification on systemd 259.5-0ubuntu3.4, including effective job timeout and
owned cleanup. Broker mount access, stop/restart storage retention and native
execution under the packaged service sandbox are qualified separately below;
broker ownership recovery and policy receipts
remain open.** The
design audit
resolves where to obtain the missing causal binding: authorize the tested exec
only after binding a waiting helper's invocation and private connection. Do not
try to reconstruct the first service invocation from terminal properties.
Reuse `ExecutionProbe`'s retained create reply, manager capture, serialization,
reference retention and recovery. The only new capability is a small native
gate/witness and its single-use local connection, not a process scheduler.

The native implementation is `tools/execution_probe_gate.c`,
`tools/execution_probe_witness.c` and `tools/execution_probe_protocol.h`.
The production install map now compiles and installs both fixed executables,
along with `execution_probe.py`, `probe_channel.py` and `probe_generation.py`.
They are not invoked by policy activation yet. The
native protocol evidence
qualifies real local exec, failure/EOF, timeout, framing and ancillary refusal
through `tests/component/test_execution_probe_native.py`; it does not qualify
manager/peer binding, broker single-use state or installed policy decisions.
Reuse these payloads and `tests.support.terminal.capture` for integration.

`probe_channel.ProbeChannel` now owns the local socket portion; its
channel evidence
qualifies one-candidate selection, kernel credential capture, supplied binding
comparison, consumed-before-send admission, interrupted-send refusal, retained
bounded results, ancillary rejection and socket cleanup. Regressions live in
`tests/unit/test_probe_channel_cleanup_safety.py` and the native component file.
`AdmissionBinding` retains caller-supplied manager/unit/job coordinates and the
selected `PeerHello`; **the adapter does not authenticate those coordinates**.
The lifecycle integration must perform the identity checks below before
calling `admit`, then validate terminal evidence after `collect`. Its `executed`
result describes a frame, never a complete receipt. `ExecutionProbe.run_native()`
now composes it with generation and manager ownership for explicit qualification;
no policy caller uses that path and the positive refusal is unchanged.

`ExecutionProbe._admission_binding` now implements the read-only manager checks,
reusing the retained `ProbeBusClient.create_reply`, pending coordinates and
finite `_request` transport. It requires an owned, usable sender and successful
matching create reply; queries the captured unique manager only; brackets unit
and service metadata plus `GetUnitByPID` with current-name-owner checks; and
matches the selected root peer's MainPID and nonzero invocation. It validates
the exact token-derived unit/description and fixed gate command, root user/group,
`Type=exec`, `Restart=no`, no additional start commands, and no configured
environment sources/overrides. Missing properties, observed replacement or
deadline expiry refuse without releasing the unit reference or closing the
client. The supported D-Bus method/property shapes were checked against the
[upstream v259 interface](https://github.com/systemd/systemd/blob/v259/man/org.freedesktop.systemd1.xml);
the installed version and binary digest are now retained by the guarded lifecycle
qualification below.

A completed start job is allowed while the selected gate waits: its retained
reply authenticates creation. If a live unit job remains, its ID/path must match
that reply. Neither case asserts an immutable first job invocation. The returned
`AdmissionBinding` is only a pre-admission identity observation; the caller must
retain it before sending once on the selected connection. Replacement after
the final read is handled by that single-use endpoint and later terminal checks,
not by claiming atomic systemd snapshots.

The `test_admission_*` regressions in
[`test_execution_probe_cleanup_safety.py`](../../tests/unit/test_execution_probe_cleanup_safety.py)
cover ADMIT-02/07's manager portion: completed/live jobs, stale/foreign peers,
unowned or uncertain replies, manager loss/replacement, same-job invocation
change, PID/unit mismatch, command/environment changes and bounded failure with
pending ownership retained. These use a synthetic manager, not real systemd.
The helper is called by `run_native()` before one admission. The ordinary `run()`
canary stays unchanged. The installed lifecycle below qualifies real systemd
binding in its selected scenario; matching native observations still retain the
`identity-unproven` refusal.

The generation owner supplies a private 0700 directory and retains its witness.
The adapter pins that directory without following a final symlink, creates
`channel` via Linux procfs's directory-descriptor path, and records its inode.
`close` removes only that socket relative to the pinned descriptor, never the
directory or witness. A replaced path, unknown inode after bind or failed unlink
returns incomplete cleanup and retains the directory descriptor for recovery;
unknown sockets are not adopted. Tests establish preservation of observed
replacements, not atomic unlink against hostile same-UID/root mutation.

`probe_generation.ProbeGeneration` supplies the outer owner. Retain it before
calling `prepare()`: it opens the fixed private runtime root, creates an exclusive
random-token directory and copies the fixed packaged witness into an exclusive
file. The source is caller-owned, regular, executable, bounded to 1 MiB and
neither group/other-writable nor special-mode; source changes during reading
refuse. The copy is mode 0500, with a frozen token/path/device/inode/size/SHA-256
identity and a retained read-only descriptor. All writable descriptors close
before preparation succeeds. No hard link to the package payload is used.

`verify()` checks the fixed root, directory, pinned witness, exact permissions,
single link, metadata and content digest. Call it before admission and terminal
comparison; failure is permanent for that owner even if paths are restored.
Immutability here relies on broker discipline and private root ownership, not
kernel sealing against hostile root. Observed replacement/mutation fails closed;
these separate reads do not claim atomic protection against same-UID mutation.

`close(settled=True)` requires the lifecycle caller's explicit attestation that
dispatch, unit, client and channel work has settled. The filesystem owner cannot
prove that attestation. Before it, witness and directory stay pinned. Cleanup
uses retained parent descriptors and recorded inodes only, never recursion or
searching for renamed paths. A missing name is insufficient if its pinned inode
still has links. Replacement, hard links, unknown identity or failed removal
retains cleanup coordinates; restoring the original permits retry without
promoting the failed attempt. A partial-write descriptor stays pinned through
removal to prevent inode reuse. Unknown creation identity requires explicit
reconciliation, never adoption of the current pathname. The runtime root belongs
to packaging/setup and is never removed by this owner.

[`test_probe_generation_cleanup_safety.py`](../../tests/unit/test_probe_generation_cleanup_safety.py)
covers source/collision refusal, partial creation/interruption, retained immutable
copies, replacement/rename/mutation, cleanup retry, concurrency and redacted events.
`test_generation_owner_retains_native_witness_through_channel_settlement` in
[`test_execution_probe_native.py`](../../tests/component/test_execution_probe_native.py)
qualifies a real local gate exec of the owner-created copy, retained digest and
cleanup after channel settlement. The fixture explicitly sets packaged 0755
source permissions instead of inheriting the host umask. Its manager binding is
synthetic; it does not qualify systemd, policy attribution or lifecycle recovery.
Payload staging and the runtime provisioning declaration are implemented below;
installed private-root provisioning and broker mount access/storage retention
are qualified below; broker ownership recovery remains unqualified.

The broker unit declares `RuntimeDirectory=oh-no-parent-control/probes`, mode
0700 and `RuntimeDirectoryPreserve=yes`. Systemd creates the directory before
broker execution, owned by the unit's root UID and sudo GID; mode 0700 excludes
group access. It stays writable inside `ProtectSystem=strict`. The
[systemd v259 directory contract](https://github.com/systemd/systemd/blob/v259/man/systemd.exec.xml)
preserves this directory on stop/restart and clears it at reboot. Systemd can
recursively correct ownership if the configured directory owner/group changes;
the supported lifecycle assumes the unchanged packaged service identity, not
hostile root mutation. No `ExecStopPost`, tmpfiles age/removal rule or package
script recursively deletes pending generations. The retained owner removes its
own settled attempt; unowned residue remains until reboot, without adoption.
This preserves evidence but does not implement broker restart recovery.

Both binaries are mode 0755 dpkg-owned payload, compiled using Debian's supplied
compiler/linker flags. Their activation digests and the broker unit/modules are
`process-restart`; the boot canary remains separately classified `reboot`.
`test_native_probe_payload_and_activation_are_complete` exercises the staged
ELF binaries' protocol refusal, permissions, module presence and exact manifest
digests. `test_packaged_broker_preserves_private_probe_runtime` checks the staged
unit declaration, not actual systemd execution. Activation tests cover additions,
changes and removal; `test_removal_preserves_unsettled_probe_generations` executes
relocated remove/purge/abort-install scripts and preserves witness identity.
Installed startup and native lifecycle success/failure are qualified below.
Broker mount writability and stop/restart storage retention have the guarded
qualification below. This does not establish broker ownership recovery.

`system_enforcement.native_probe_storage_lifecycle` and
`test_native_probe_broker_storage_lifecycle` qualify the actual running broker's
mount namespace, without adding a product test API or changing its unit.
`_in_broker_mount` brackets namespace/root descriptor capture with the active
service's MainPID/InvocationID and requires effective `ProtectSystem=strict`
and `RuntimeDirectoryPreserve=yes`. A joined worker thread uses supported
[`unshare(CLONE_FS)` and `setns(CLONE_NEWNS)`](https://docs.python.org/3.13/library/os.html#os.setns),
then enters the pinned root, so absolute paths cannot retain the caller's old
root mount. It checks namespace identity and the read-only `/usr` mount before
creating or verifying a generation. Only that worker's filesystem state changes;
the fixture never signals a PID discovered from service metadata.

The fixture retains the original `ProbeGeneration` outside the broker, proves
`close(settled=False)` refuses collection, and verifies its exact identity/content
after stop, start and restart. Verification runs inside each new broker mount;
a fresh generation remains independent of the retained one. Both owners settle
without dispatching a unit or opening a channel. Local regressions in
`test_system_enforcement_cleanup_safety.py` cover guest/identity refusal,
namespace failure, joined-worker/descriptor cleanup, lifecycle interruption and
replacement preservation with an explicit owned retry.

The first storage qualification, 2026-09-14, passed in
`/tmp/onpc-system-zk0l5jew/evidence/result.json` and sibling
`../guest-results/enforcement.xml`: all four package/reboot prerequisites and
the selected storage case passed, with no failures/skips; collection, cleanup
and full restored backing-byte verification passed. The
 This qualifies mount access and
unchanged-identity runtime-directory preservation, not all broker capabilities/
seccomp restrictions, pre-terminal loss settlement, restart adoption, in-flight
dispatch across broker death or policy attribution. The original owner survives
in the test fixture; a restarted product broker does not regain that owner.
This is test-only integration (`none` activation), with no saved-data change.

`system_probe_sandbox.native_probe_broker_sandbox` and
`test_native_probe_broker_service_sandbox` now qualify native success,
withheld-admission recovery and fresh success under the packaged broker's
complete configured execution restrictions. The guest-only fixture adds one
unprefixed `ExecStartPost` command through an exclusively created runtime drop-in;
it changes no existing unit directive, broker entry point or product API.
`PrivateTmp` hides the normal runner input directory, so `stage_inputs` copies
only the verified transfer inventory into the existing private probe runtime
root. The worker runs the unchanged guest guard against that copied closure.
No bind mount, extra writable path or security exemption is introduced.

Before dispatch and after restoration, the fixture compares all packaged
execution-restriction properties. The worker compares effective bounding,
effective and ambient capabilities, seccomp and no-new-privileges state to the
broker process; requires its service cgroup and a read-only `/usr`; and proves
an Internet socket is refused. It reuses `native_probe_lifecycle` for native
identity, refusal, finite recovery and generation cleanup. Worker diagnostics
join the normal private collector. Restoration removes only the recorded drop-in
inode with its exact written bytes and requires an active restored broker.
Observed directory/file replacement or mutation refuses restoration and leaves
outer guarded recovery responsible; this is not atomic protection against
hostile root. Transferred fixture copies remain owned by outer baseline cleanup.
`test_system_probe_sandbox_cleanup_safety.py` covers guest refusal, copy/collision
boundaries, interrupted/partial writes, replacement preservation, effective
restriction failures and retained worker evidence.

Sandbox attempt 1 passed on 2026-09-14 at
`/tmp/onpc-system-t5ira6cj/evidence/result.json`, with assertions in sibling
`../guest-results/enforcement.xml`: all five installed executions passed with
no failures/skips. Every native stage settled with the effective 4,000,000 µs
job timeout; both positive stages remained `identity-unproven`. Drop-in
restoration, outer collection/cleanup and full restored-baseline byte verification
passed. This qualifies the adapter in a
separate service start-post process, not broker event-loop integration, restart
adoption/in-flight recovery, earlier sender-loss settlement or rule attribution.
The new fixture integration has activation `none` and no saved-data change.

`ExecutionProbe.run_native()` now retains the generation before preparation and
the channel before socket creation. It uses the fixed gate with only the validated
generation token, authenticates the selected peer, verifies the witness, and
retains `ProbeResult.generation`, `admission` and bound invocation before calling
`admit()` once. A shared monotonic deadline starts before dispatch and constrains
`ProbeBusClient.poll_create(deadline=...)`, `ProbeChannel.select(deadline=...)`,
manager reads and the admission send. Cleanup polling may continue later, but
can never select or admit a late/replacement peer.

After a frame, the lifecycle compares final invocation, command and expected
exit, rechecks generation content and the manager owner, then retains
`native_verified` only as a diagnostic observation. `executed` remains false;
neither that flag nor a positive frame is a policy receipt. A frame retained by
the channel just before an interruption is copied into pending evidence before
channel cleanup, without outcome promotion. `recover()` never prepares, selects,
admits or recollects; it only settles the retained dispatch/unit/client and
filesystem owners. Generation cleanup waits for proven unit settlement, closed
client and completed channel cleanup, including retries after interruption.

The `test_native_*` lifecycle regressions in
[`test_execution_probe_cleanup_safety.py`](../../tests/unit/test_execution_probe_cleanup_safety.py)
use the real filesystem owner with synthetic channel/manager services. They
cover retained binding/frame/terminal evidence, interrupted preparation/send/
collection/cleanup, shared deadlines, missing replies, terminal replacement,
bad exit/frame, witness mutation and each owner's cleanup refusal. The separate
Gio client suites qualify native command serialization and late replies over a
real private bus; native component tests qualify actual gate/channel/witness
execution. These separate local scopes do not establish installed behavior;
the guarded composition below supplies that evidence for the selected lifecycle,
but not policy attribution or broker restart.

The guarded `test_native_probe_systemd_lifecycle` now registers one continuous
success/withheld-admission/fresh-success scenario through
`system_enforcement.native_probe_lifecycle`. It verifies installed private-root
provisioning, captures systemd/fapolicyd identities and retains initial and pending
probe coordinates in JUnit. The failure variant validates the real binding before
withholding admission; recovery must settle the same adapter and generation.
Host collector regressions cover guest refusal, failed assertions, interruption
and bounded incomplete cleanup without replay or name-based process operations.
This guest-root scenario does not qualify the broker's service namespace or
stop/restart preservation.

The first live run, `/tmp/onpc-system-7owbex3p/evidence/result.json` and sibling
`../guest-results/enforcement.xml`, passed all four package/reboot prerequisites
and private-root provisioning on systemd `259.5-0ubuntu3.4` / fapolicyd `1.3.6-1`.
Creation returned `create-uncertain`, without a job, frame or terminal identity;
bounded adapter recovery remained incomplete. The outer runner collected evidence,
restored the baseline and verified cleanup. Refusal and fresh-success stages did
not execute. The creation error's cause is **unknown**: the old callback discarded
its D-Bus name, and the retained scoped service journal contains no probe entry.

`ProbeCreateReply.error_name` and `ProbeResult.create_error_name` now retain only
`CREATE_ERROR_NAMES`' fixed standard D-Bus names, with all other errors represented
as `other`; no arbitrary name or message is retained. `_collect_create` copies this
diagnostic through recovery without changing uncertain-create settlement, collision
handling, admission or receipt eligibility. The late-reply safety regression tests
every listed name, private-name redaction and retained ownership; the private-bus
client suite still passes. This observability addition is locally verified and
was **not** in the first failed VM artifact. The second live run,
`/tmp/onpc-system-2vsowz65/evidence/result.json` and sibling
`../guest-results/enforcement.xml`, identifies
`org.freedesktop.DBus.Error.PropertyReadOnly` on the same systemd version.
All four prerequisites passed; creation again had no job/frame/terminal evidence,
adapter recovery stayed incomplete, and outer collection/restoration/full backing
verification passed. This is an API property rejection, not an authorization
denial or a successful lifecycle. It does not identify the rejected property by
name or establish that an uncertain dispatch owns no resources.

The source audit makes `JobTimeoutUSec` an actionable candidate: the
[v259.5 transient setter](https://github.com/systemd/systemd/blob/v259.5/src/core/dbus-unit.c#L2207)
omits its return and falls through to zero; `bus_unit_set_properties` maps an
unhandled property to this exact error. This explains the observed error class,
but the installed property identity remains inferred. Do not replace it with
`JobRunningTimeoutUSec` alone: the
[public timeout contract](https://github.com/systemd/systemd/blob/v259.5/man/systemd.unit.xml#L1030)
distinguishes queued-job time from running-job time.

The locally implemented correction is a package-owned
`onpc-execution-probe-.service.d/` drop-in with `[Unit] JobTimeoutSec=4`, retaining
the existing service deadlines and sender/admission/cleanup guards. The
[public prefix drop-in contract](https://github.com/systemd/systemd/blob/v259.5/man/systemd.unit.xml#L184)
and v259.5 `unit_load_fragment_and_dropin`, `unit_load_dropin` and
`config_parse_job_timeout_sec` support this route: transient fragment loading
returns loaded, then drop-ins are parsed through the unit-file timeout parser.
`_properties` no longer submits the defective setter. `_admission_binding`
requires both unit snapshots to report exactly 4,000,000 microseconds;
`_snapshot` also checks both readings before a positive diagnostic, while retaining
terminal evidence for owned cleanup even when the timeout is missing or overridden.
`ProbeResult.job_timeout_usec` retains the effective collection value. The
installed collector requires that value after settlement in every lifecycle stage.

The local regressions
`test_native_effective_queue_timeout_refusal_keeps_owned_cleanup` and
`test_admission_rejects_timeout_changed_across_bracket` cover missing, disabled,
shortened, extended, infinite and changing values, with no admission on failure
and retained cleanup. Package payload and activation tests verify mode, contents,
digest and addition/change/removal activation. The drop-in affects the fixed
boot canary too, so its [activation class](../Publishing.md#package-update-activation)
is `reboot`; dpkg owns removal. Service deadlines and sender ownership stay intact.
Readback does not retroactively bound an already queued job under a missing or
overridden drop-in; uncertain attempts still require retained recovery.

**Installed composition attempt 3 passed** at
`/tmp/onpc-system-jq_9bl4m/evidence/result.json`, with stage properties in sibling
`../guest-results/enforcement.xml`. Fresh artifacts used the locally qualified
[source-selection exception](../../tests/integration/README.md#package-and-fixture-inputs).
On systemd `259.5-0ubuntu3.4` / fapolicyd `1.3.6-1`, all four package/reboot
prerequisites and `test_native_probe_systemd_lifecycle` passed without skips.
Both success stages retained `native_verified`, executed channel frames and
terminal observations, while deliberately withholding admission produced
`observation-failed` with no native witness and retained pending ownership.
Recovery settled that same adapter; a fresh generation then succeeded. All three
stages reported `JobTimeoutUSec=4000000`, completed client/reference/generation
cleanup and left the private runtime root unchanged. `executed` stayed false:
these are native lifecycle diagnostics, not policy receipts. This qualifies the
packaged timeout correction for this installed scenario; the exact property
rejected by attempt 2 remains inferred. Both earlier failures remain retained.
Outer collection/restoration and full backing-byte verification passed. The
separate storage case above now qualifies broker mount writability and stop/
restart storage preservation. The [sender-loss case](#settlement-after-permanent-sender-loss)
now qualifies settlement after terminal evidence; earlier loss, broker ownership
recovery and policy attribution remain unqualified; do not extend either
selected result to those boundaries.

The wire frame is exactly 40 bytes: `ONP1`, one stage byte (`H` hello, `A`
admission, `X` executed, `F` exec failed), three zero reserved bytes and the
32 lowercase hexadecimal, nonzero invocation ID. Admission requires write EOF
after exactly one matching frame; the broker must half-close after sending it.
This lets the gate reject extra or delayed data before exec. Gate connect/hello/
admission/send share a two-second monotonic deadline; the witness has a separate
two-second output deadline. All socket I/O is nonblocking. Received ancillary
descriptors are closed and rejected, including control-buffer truncation.

The gate accepts only a nonzero 32-hex attempt token, using fixed
`/run/oh-no-parent-control/probes/<token>/channel` and sibling `witness` paths.
Runtime root and attempt directory must be caller-owned mode 0700; the regular,
non-symlink witness must be caller-owned, owner-executable and have no write bits.
The intended service caller is root. Local tests relocate the compile-time
runtime root and use the test caller; no runtime path override or arbitrary
command is exposed. The connected descriptor becomes fd 3, other descriptors
above the standard streams close before pathname exec, and the witness receives
an empty environment. The gate checks the server's peer UID against its own;
this does **not** supply the broker's pending manager/unit/peer validation below.
The generation owner binds the witness digest locally; the lifecycle caller
retains and revalidates it through terminal collection. Native preflight alone
is not that proof.

The native transient service requests the fixed gate, under the existing
systemd ownership and finite service deadlines. The gate creates its own Unix
stream connection to a broker-created listener in a fresh root-only runtime
directory, sends a bounded hello containing its systemd `INVOCATION_ID`, then
waits. It neither forks nor executes the tested target before admission. The
broker accepts at most one candidate connection for that attempt and checks
kernel `SO_PEERCRED` UID/PID, captured manager and returned job, exact transient
unit/command metadata, MainPID and a stable nonzero InvocationID against the
hello. It uses these PIDs only for identity comparison, never signaling. The
helper is trusted packaged code; a hello alone or a numeric PID alone is not
an identity receipt. Environment overrides of invocation identity are forbidden.

Bind this tuple in pending state **before** sending the one admission message.
Mark admission consumed before the send, including partial-send/interruption
paths. Never select another connection, resend admission or reconnect during
recovery. After admission, the gate calls ordinary pathname `execve` on the
exact fresh, root-owned generation witness, in the same process. Only its
connected descriptor survives into the witness; it is not passed to systemd,
shared through a unit FD store, inherited by another process or transferred with
SCM_RIGHTS. The native witness emits the execution frame and exits with the
specified status. The gate cannot emit that frame: failed exec emits a distinct
failure or closes the channel. No shell, interpreter, arbitrary command/argument
dispatch, fd-based execution bypass or policy-wide allowance is introduced.
The gate itself must be executable under the existing policy; failure is a
failed probe, not permission to exempt unrelated executables.

Use a versioned, fixed-size, bounded protocol and finite nonblocking waits for
connect/hello/admission/result. Reject malformed, truncated, extra or wrong-stage
data, unexpected descriptors, wrong peers and deadline expiry. Bind the exact
fresh path and content identity to the generation before admission; keep them
immutable until settlement. Only the witness entry point in that executable
may produce the execution frame on the admitted connection. A token, path,
output file or environment value alone never proves execution.

This defines the **first authorized target exec**, not the first systemd wrapper
invocation. A wrapper replaced before any admission cannot have executed the
target. Once a connection is selected, its loss/replacement fails the attempt;
even a same-job rerun cannot obtain another admission. A restart after admission
cannot inherit the old connected endpoint, and cannot overwrite retained frames.
Final terminal evidence must still match the invocation bound before exec,
expected exit and all existing unit/reference/client cleanup gates. A positive
frame followed by timeout, changed invocation or uncertain cleanup is failure.
This does not restore positive results to the current fixed-canary adapter;
its `identity-unproven` refusal remains until this different execution path is
implemented and qualified. Recovery never promotes an earlier failed attempt.

The broker closes only descriptors it created/accepted, and removes only its
recorded socket/directory identities. Channel closure, EOF and unlinked sockets
are not process termination or dispatch-settlement evidence. Retain the existing
pending sender/unit coordinates through ambiguous dispatch and stuck tasks;
finish their cleanup before reporting success. Broker restart loses admission
state and therefore cannot resume a positive receipt or replay admission.
Ownership recovery across broker restart remains a separate integration gate.

Qualification must cover pre-admission replacement, same-job rerun, fast exec,
denied exec followed by replacement success, partial admission, late replies,
foreign/duplicate peers, PID reuse, malformed frames and all cleanup failures.
The audit owns the complete executable case matrix; the native evidence maps
only the implemented portions. The channel evidence adds local single-use,
interruption, supplied-peer mismatch and socket-identity cleanup qualification.
Manager/unit authentication now has the synthetic-manager regressions above;
the selected installed lifecycle now covers success and withheld-admission
recovery. Live PID reuse, systemd replacement and broker restart recovery remain
unqualified. The packaged boot canary stays unchanged.
Any new installed payload uses `process-restart` activation; fresh runtime
objects are not saved application data. Packaging/removal cleanup must ship with
the payload. Full policy acknowledgement still additionally requires the
generation gate's rule-attributed allow/deny decisions, daemon/compiled-input
binding and forward/rollback/removal checks; this channel proves none of those.

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
