# Logging, diagnostics, and feedback

[System design overview](../System-Design.md)

Read this for component events, privacy at logging call sites, diagnostic
archives, the feedback editor, and HTTP submission/retry behavior.

Implementation: [logs.py](../../broker/oh_no_parent_control/logs.py), [broker service unit](../../data/systemd/oh-no-parent-control-broker.service), [feedback.py](../../common/oh_no_parent_control_ui/feedback.py), [feedback_transport.py](../../common/oh_no_parent_control_ui/feedback_transport.py), [rich_text_editor.py](../../common/oh_no_parent_control_ui/rich_text_editor.py), [diagnostics.py](../../common/oh_no_parent_control_ui/diagnostics.py).

## Logging

Automatic diagnostics must exclude PII. Customer-written feedback, reply
email, and explicitly selected file attachments remain supported and separate
from automatic diagnostics. There is no automatic harvesting of those inputs.

The broker is the sole event-file writer. Validated records live under
`/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.events`, owned by
`root:sudo`, with directories `0750` and files `0640`. Parent, child, and kiosk
forward structured envelopes over the existing role-checked D-Bus `LogEvent`
method; broker events are emitted internally. Human-readable logging prefixes
are `onpc.<domain>` throughout the applications and runtime helpers.

Each component retains three available dates, with three 256 KiB segments per
date. Identical events within 60 seconds are suppressed and counted. Child
countdown observations are sampled every five minutes, with increases and
transitions to/from zero retained. Routine per-second remaining-time D-Bus
dispatch/completion messages are omitted; errors are retained. An error, invalid
grant, clock divergence, or unattributed grant increase pins
the preceding 40 records per component into that date's bounded incident file.
The latest incident replaces the previous one; error context has priority over
ordinary history when export limits require trimming. Counters describe
suppression, rotation, incidents, failed writes, invalid input, truncation, and missing
component directories. In-memory counters describe the current broker process.

`kiosk.timing` records bounded monotonic elapsed durations for background, lava
and scenery construction, complete configured-form painting/presentation and
the request's preference-save/dispatch stages. Artwork durations cover their
own work; form durations start at Python module loading, excluding PAM and
interpreter bootstrap; request durations start at submission. Form completion
requires loaded accounts/settings/language, a settled estimate/transition, the
request page and no owned modal. `form-presented` is emitted only when GDK
supplies actual presentation feedback; `form-painted` alone does not establish
display visibility. No raw clock, frame counter or account identity is logged.
The request application's read-only session-bus `KioskTiming1.GetStartupTimings`
method supplies Python-start, first eligible paint and available presentation
monotonic nanoseconds to engineering probes. Zero means unavailable. This
separate witness performs no UI or broker action and accepts no timestamps;
it reuses the Application UI transport's asynchronous same-UID credential check,
bounds pending checks and retires them on application D-Bus teardown;
readers pin its live bus owner to the current app service/process and boot.
Absolute clocks stay in private probe evidence, outside automatic diagnostics
and feedback. Registration follows the application's D-Bus lifetime.
Witness-registration failure leaves the ordinary request UI available and emits
the fixed `kiosk.timing-unavailable` diagnostic.

Countdown troubleshooting also retains `child.countdown-sample` once a minute,
on estimate-source changes, zero transitions and deadline increases exceeding
two seconds. It records the native and fresh timer remaining durations, the
selected input and broker result, the previous verified remaining duration,
and monotonic refresh/broker/observation intervals. `child.countdown-state`
records changes in loaded, limit-enabled, native-deadline-available, locked and
greeter booleans, with the native and panel remaining durations. These distinguish
a moving timer estimate, a cached native deadline and an already locked desktop.
They do not assert that a native deadline is fresh or identify who caused a lock.
All operands are bounded durations or closed categories derived from the existing
countdown calculation; raw deadlines, usage intervals and account/session
identities are excluded. No extra timer or policy query is made for logging.
Diagnostic failure cannot interrupt a successful refresh, countdown or lock.
`child.resume-refresh-deferred` distinguishes a temporary resume usage-query or
usage-replay failure with a finite positive native deadline from a reported
error: it records only the reviewed operation stage and transient category,
explicitly retaining the native countdown and deferring usage replay until the
next inactivity transition.
Repeated active failures at the same stage use `child.resume-refresh-failed`
from the third occurrence and open one report until active recovery or a limit
lifecycle change. Their counts survive healthy idle refreshes because ordinary
countdown and idle reads cannot prove that resume-only query/replay is healthy.
Inactive retry diagnostics, permanent errors, and exhausted estimate reads
retain their existing events and reporting behavior.
`adapters.usage-query-failed` preserves the final reviewed category from the
broker's identity-scoped usage helper after bounded read retries or a permanent
failure. Its fixed exit-status protocol excludes raw exception text and account
identities; the existing generic helper-failure event remains readable.
The additive catalogue ships with the child and broker; session renewal and
broker process restart load the new diagnostics. No saved-data migration is needed.

### Native login and unlock observations

The child [session observer](../../child/sessionDiagnostics.js) emits
`child.session-state` when the native limit decision, logind activity/idle/locked
hints or Shell locked/greeter mode changes. It records the native state category,
`shouldLockSession`, whether parental limits and the session proxy are available,
and the bounded native remaining duration. Duration ticks alone produce no event.
These observations distinguish a successful password check from a native unlock
refusal or a later lock. They do not infer password success from an unlocked mode.

Only `Lock`/`Unlock` signals from the current session proxy's current logind owner
produce request observations. Each unlock increments a process-local attempt
counter, retaining identical successive requests despite duplicate suppression.
A single owned one-second timer records the resulting state and monotonic elapsed
duration. Another request, a Lock signal, suspend, owner replacement or extension
shutdown retires the previous observation timer. The observer records no account,
session, bus-owner or device identifiers, passwords, raw deadlines or error text.
It never performs a lock/unlock or changes a hint, policy or native state.

`child.session-monitor-failed` explicitly reports unavailable observation.
`child.failure` retains the built-in exception type and reviewed error category
with separate session-monitor attach, signal, observation and cleanup operation
labels. Unlock continuation similarly distinguishes startup, signal handling,
native dispatch, observation and cleanup; locked keyboard-focus recovery records
its own operation. These optional helpers use the shared diagnostic projection
without opening an error report, exposing session/device identities or changing
native admission. A diagnostic transport failure remains isolated.
Observer failures cannot interrupt native signal dispatch or child enforcement;
all connections and the timer are retired on failed startup and disable. The
additive catalogue ships with the child and broker. A child session renewal loads
the observer; the broker reloads the catalogue on process restart. Existing event
formats and saved data are unchanged.

The separate [unlock continuation](../../child/sessionUnlock.js) emits
`child.unlock-recovery` for arming, its single native continuation, observed
unlock, pending cancellation, expiry or failure. `native-owned` records an
already observed native unlock animation. After dispatch, `observed-interruption`
and `observation-expired` explicitly distinguish observation from cancellation:
GNOME's public API cannot retract its own pending native completion callbacks.
It records a local request ordinal,
closed cancellation reason, monotonic elapsed duration, native lock decision,
actual public shield lock state, session activity and bounded remaining time.
These distinguish a discarded native Unlock from a completed recovery and an
uncompleted native call. There is no credential or identity in these events.
`child.unlock-recovery-unavailable` identifies setup or observation failures;
diagnostic failures never authorize or prevent a continuation. The
[admission contract](Screen-Time.md#countdown-and-expiry-enforcement) owns its
authority and cancellation rules. The new module activates at session renewal.

### Event timestamps

Every new record includes the broker's UTC observation time as an ISO 8601
timestamp with milliseconds and `Z`, for example `2026-09-12T18:42:03.337Z`.
Readable exports place it immediately after severity. Source and incident file
dates use UTC too. Monotonic elapsed offsets remain supplementary timing data,
so clock corrections do not change elapsed durations or event sequence ordering.
The timestamp field is additive: retained records and schema-3 reports without
it remain readable, with their original elapsed offsets and source dates; their
missing UTC times cannot be reconstructed. No stored logs are rewritten and no
preference migration is required. The broker loads the writer on process restart;
frontends load the updated timestamp validator on their next launch. Ship these
changes together. The generic portal attachment contract is unchanged.

Existing `.log` files are never imported, exported, modified, or pruned by the
new diagnostic pipeline. No journal, raw subprocess output, saved preference
file, application inventory, or other arbitrary file becomes an attachment.

### Kiosk admission diagnostics

The PAM module and fixed-purpose login helper emit local journal/syslog records
with the `onpc.pam` prefix before the kiosk application can start. These are
integration diagnostics. The broker projects only the reviewed closed-field
records described below into feedback; raw journal text is never attached.
Inspect local raw records using the maintained system diagnostics reader.

Routing records identify the account or session stage, allowed/denied/
unavailable outcome, dedicated/other/unset session category, wayland/other/unset
transport category, none/restored/failed default recovery, and a fixed failure
reason (timeout, bus-failed, identity, verification or unavailable). Native records
also identify denied services, unsafe/busy locks, an unbound session check and
numeric PAM results, helper failure and helper timeout. Successful preference
checks are retained so a missing session-stage record can distinguish an
interrupted login from completed preference validation. These records do not
attest to GDM's next executable; the final native boundary owns that check.
Wrong saved defaults produce stage records. Recovery never changes the failed
attempt into an allowed login.

The final native boundary emits `onpc.pam kiosk execution-boundary` with an
armed or denied outcome. Integrity failures use the fixed `integration` reason.
Preparation emits `onpc.kiosk confinement preparation` with a denied outcome,
a closed manager/gate role and preparation stage, a fixed failure reason and
the last failing source line in the shipped preparation helper. Stages separate
account identity, attestation/payload, enforcement, executable/privileged
inventories, directory layout, manager generation, runtime/recovery, generation
creation/verification and binding publication. Reviewed reason tokens identify
trust, missing executable, inventory, generation and policy failures; unknown
errors remain `verification`. OS failures include bounded numeric errno;
command failures/timeouts identify their category and bounded exit status,
without command arguments or captured output. The retained
`stale-manager-reboot-required` and `generation-limit-reboot-required` reasons
require reboot rather than automatic process termination. A separate
`onpc.kiosk confinement directory-view` record reports the aggregate number of
writable or non-root-owned sibling directories hidden behind empty private
directories, with
`outcome=masked reason=writable-sibling-directory`. It contains no directory
names and does not assert completed admission. Unavailable diagnostic output
does not change the preparation result.

`onpc.kiosk confinement directory-entry` adds aggregated mask, omission or
refusal classifications for ownership, access, entry kind, required/sibling
scope, broad system area and the closed reason. Untrusted sibling files/links,
special types, separator names and unavailable metadata can be omitted
without exposing their contents; required inputs must still fail closed. The
alias ancestry and UTF-8 publication repairs passed host acceptance in
[task 002a](../Kiosk-Prompt.md#ambient-classification-and-required-input-controls--002a).
Neither classification record includes the entry name or full path.

The native PAM caller adds a separate `onpc.pam kiosk native-view` record for
private-view failures. The existing `execution-boundary` and `cleanup=failed`
records retain their format and meaning. Cause production is separate from the
collector projection owned by task 002 of the
[entry plan](../Kiosk-Prompt.md); the new record alone does not establish that
feedback contains its cause.

The producer schema is fixed, with no optional or arbitrary text fields:

```text
onpc.pam kiosk native-view outcome=denied role=manager stage=manifest reason=manifest errno=-1
onpc.pam kiosk native-view outcome=denied role=gate stage=bind reason=mount errno=13
onpc.pam kiosk native-view outcome=cleanup-failed role=gate stage=detach reason=identity errno=-1
```

These sanitized examples illustrate independent records, not a single admission.
`outcome` is `denied` for the primary native failure or `cleanup-failed` for an
independent owned-cleanup failure. `role` is the validated service-derived
`manager` or `gate`. Closed stages are `namespace`, `staging`, `manifest`,
`structure`, `source`, `bind`, `attach`, `readonly` and `detach`; closed reasons
are `manifest`, `metadata`, `identity`, `namespace`, `mount`, `readonly` and
`detach`. The stage identifies the operation; the reason distinguishes invalid
records, unsafe metadata, identity mismatch and kernel operation failure.
`errno` is a directly observed error number from 1 through 4095, or -1 when
unavailable, out of range or a validation comparison failed. Never infer an
error number from a successful call's leftover state.

Each invocation retains its first primary failure and first cleanup failure,
emitting at most two cause records at the final PAM boundary. Success emits no
cause record. No names, paths, inode/mount/account identities, manifest contents
or system error text enter these records. Logging preserves the caller's error
state and cannot change admission or cleanup results. Host fixture witnesses
cover cause production; installed behavior and archive composition keep their
separate acceptance obligations.

Before a feedback snapshot, the independent
`collect_kiosk_admission_diagnostics()` reader projects exact reviewed native
PAM, login-helper and preparation records. It runs even without a surviving
kiosk manager, valid kiosk configuration or normal policy readiness. A separate
five-second budget covers one bounded journal read of the last 24 hours across
retained boots, at most 200 matching entries and 20 exported markers. Denials
and unavailable/error outcomes take priority over later successes when clipping;
retained markers keep source chronology. This does not recover unavailable or
already-rotated journal history.

`kiosk.admission-journal` records source UTC time, producer category, manager/gate
role where known, stage, outcome, closed reason, session/transport/recovery
categories and bounded numeric status, errno and shipped preparation source line.
An absent status is -256, errno is -1 and source line is 0. Its exact native
passwordless marker separates successful authentication from later routing or
session-preparation failure. Success at one stage never attests completed entry.
`kiosk.admission-directory` retains the aggregate entry classifications without
names or paths. `kiosk.admission-observation` reports complete, partial or
unavailable with retained, recognized, rejected and dropped counts. Complete
describes this bounded read only; rejected records, a full tail or marker clipping
make the observation partial.

Projection requires root journal credentials, reviewed native executable paths,
or the reviewed Python/helper executable, identifier and unit provenance.
Unknown/spoofed messages and fields are not exported. Journal account/process/
session/host/boot identities, raw messages, arguments and arbitrary exception
text remain transient. Source timestamps and closed failure categories allow
report-only diagnosis without turning those identities into attachments.

Configuration/removal reports a bounded fixed
reason token and retains ownership records on failure. It also identifies the
last failing source line in the shipped confinement integration, numeric OS
errno or command exit status, and closed policy-command/module categories.
Unreviewed PAM session modules report `unsupported-pam-session-module`; the
reviewed diagnostic categories distinguish `pam-cgfs`, `pam-exec` and `other`.
These categories do not change the supported module inventory. Arbitrary module names, paths,
arguments and exception text remain excluded. Policy compiler errors
may appear in local package-manager output. These are local engineering
diagnostics, not feedback attachment fields.

No username, UID, session ID, arbitrary desktop name, metadata value, command
stderr or exception text is formatted by these call sites. System journal
envelopes remain operating-system data and are not approved automatic exports.
These diagnostics and the confinement guard activate with the changed PAM
profile at the required reboot; an already running desktop is not terminated.

### Kiosk startup crash diagnostics

Feedback collection additionally projects reviewed kiosk renderer, security and
session-journal markers through
[dependency_diagnostics.py](../../broker/oh_no_parent_control/dependency_diagnostics.py).
This read runs before the report snapshot, including diagnostics-only mode, and
does not need a surviving kiosk application or user manager. It reads this boot's
last 24 hours within a shared five-second budget, at most 200 matching entries
and 20 exported markers per source. Collection reports complete, partial or
unavailable separately for each source; complete describes the bounded read,
not complete historical evidence. Configuration failure reports unavailable
identity without querying another account. There are no service, session,
renderer or policy changes.

`kiosk.session-journal` retains source UTC times and closed categories for
SELinux's enforcing kiosk-app GPU device mapping denial, Vulkan memory mapping
and permission failures, a Mesa segfault, the app's numeric exit/signal result,
its failure-triggered shutdown and the dedicated session target stopping.
Renderer and systemd records require the configured kiosk UID and reviewed
executable/unit provenance. Security records require trusted audit/kernel
transport and exact reviewed policy contexts; Mesa fault correlation uses only
transient PIDs from the observed renderer. A GPU map denial followed by Vulkan
mapping failure, Mesa crash, signal 11 and the app's OnFailure shutdown supports
a renderer confinement diagnosis. Source times relate these observations;
unrelated security denials do not establish the cause of a session exit.

Raw journal messages, exception text, host/account/process/session/device
identities, paths, addresses and stack traces are discarded, never attached.
PAM routing and preparation have the separate bounded projection described above.
These additive catalogue entries ship with all validators. The broker loads
the collector after `process-restart`; new frontend processes load its catalogue.
No saved-data migration or feedback transport change is required. Archive and
privacy coverage lives in [diagnostics tests](../../tests/unit/test_diagnostics.py)
and [service contracts](../../tests/unit/test_service_contract.py).

### Schema and field provenance

[diagnostic_catalog.json](../../common/oh_no_parent_control_ui/diagnostic_catalog.json)
is the shipped, versioned allowlist: stable event IDs, fixed text, permitted
components, exact field names, closed enums, booleans, and bounded numbers.
[diagnostic_events.py](../../common/oh_no_parent_control_ui/diagnostic_events.py)
validates before creating a Python LogRecord. The child uses the same catalogue
through [diagnosticEvents.mjs](../../child/diagnosticEvents.mjs). Storage validates
again, export rebuilds approved records, and the frontend and HTTP sender
revalidate the report. Unknown text, extra fields, and legacy payloads fail
closed. Unknown enum values become the fixed category `other` at the producer.
Foreign Python log records become a fixed suppressed-event marker without
formatting their arguments or exceptions.

Child-extension diagnostics identify the fixed command tool, settings key and
live-session/offline transport on every distribution; no Fedora or OS-identity
gate controls these events. Activation records include Shell availability
and global-switch recovery context. Settings read-back and rollback record the
key, verification stage and match result; runtime verification records only
configured/active booleans. Command stderr is inspected transiently for reviewed
warning markers and reduced to closed categories (dconf commit, service
activation, access, read-only storage, runtime, schema, writability or memory
backend failures). A zero exit status does not suppress those warnings. Unknown
stderr becomes `other`; no raw text, argv values, extension lists, usernames,
UIDs, paths or exception messages are logged. Commands keep the existing locale
but use C message translations so classification is stable. These observations
do not change activation or rollback acceptance. The broker loads them after
`process-restart`; ship the additive catalogue with all frontend validators.
Activation and rollback exceptions also record their reviewed shipped-module
category and source line before conversion to the public broker error. This
preserves the original failure location as well as any separate rollback
failure, without recording exception text or traceback details.

Offline `dbus-run-session` daemon failures also emit
`extension-manager.session-bus-failure`, independently of the dconf warning and
subprocess exit status. The closed `selinux-netlink-family-unavailable` reason
identifies SELinux AVC monitoring's unsupported netlink address family and
directs investigation to the command's address-family sandbox; other recognized
daemon exits use `startup-failed`. A successful settings-command exit does not
establish that its bus started or its write committed. The existing commit
warning, setting verification and rollback records remain separate evidence.
Only fixed C-locale stderr markers and reviewed command/key/transport categories
enter the event; daemon PIDs, raw stderr and account information are excluded.
This diagnosis is generic across distributions with SELinux-enabled D-Bus;
it does not change the broker sandbox, commands, verification or rollback.
Ship the additive catalogue with all validators; the broker loads this logging
on process restart, and new frontend processes load the updated catalogue.

The child extension's `child.lock-focus-sync` event records only `complete` or
`failed` for the GNOME 50 locked-session device-focus compatibility hook. The
outcome comes from the synchronous notification result; neither device
capabilities nor device, window, account or session identities enter the event.
Exceptions are discarded without formatting. Ship the additive catalogue with
the child and broker validators; child session renewal and broker restart load
the new producer and catalogue.

Diagnostic export also observes eligible live child sessions through GNOME's
public `GetExtensionInfo` interface, before taking the log snapshot. This catches
module import failures that prevent the extension's own logger from loading.
Live activation failures collect this evidence before rollback too. One shared
eight-second budget bounds the session and policy commands; unavailable probes
are recorded without preventing export. No extension or settings mutation is
performed by collection.

`extension-manager.load-state` projects only closed Shell state, shipped module
and failure categories. For recognized shipped `.mjs` import failures,
`extension-manager.payload-policy` records the JavaScript file-type category,
presence in fapolicyd's trust database, trust-filter decision, and presence of
the reviewed trusted-language rule pattern. An operation-not-permitted import
with absent trust, an excluding filter and trusted-only JavaScript rules points
to a packaged payload trust-filter mismatch. Listed rules and database reads do
not acknowledge the daemon's active generation. Missing tools or incomplete
queries remain `unknown`, never an assertion of absent trust. Shell error text,
paths, account identifiers, trust hashes and other database/rule contents are
discarded. These read-only observations are generic across supported desktops;
unsupported fapolicyd query interfaces produce unknown fields. Activation and
rollback acceptance remain unchanged. Ship the additive catalogue with all
validators; the broker loads the collector on process restart.

Allowed sources include operation outcomes, duration calculation operands,
counts, packaged app version, elapsed operation timings, and fixed dependency
states. Random request references correlate a single approval across components;
they never derive from a person, account, session, or device. Local diagnostic
segments are generated independently of OS identifiers and are renumbered in
the export. Events carry UTC observation timestamps and elapsed offsets. Grant observations additionally
include the local observation date/time to millisecond precision with a numeric
UTC offset, as explicitly requested for investigating external grants. This is
the broker's observation time, not the grant's issuance time or the exact time
of a button click. Raw grant and OS boot/session timestamps remain excluded.

Forbidden sources include names, usernames, UIDs, email addresses, attachment
names or contents, home paths, command lines, raw environment variables, URLs,
hostnames, network addresses, device IDs, application titles/paths, credentials,
exception messages, and traceback filenames/source/locals. Hashing or replacing
these with stable pseudonyms is not an allowed workaround. Error diagnostics
contain closed error categories and, when available, a shipped module category
and source line number; they never format an exception.

A bounded integer type does not establish privacy: reviewers must examine its
source. New logging requires a catalogue entry, a call-site provenance review,
and privacy regression coverage. Do not reuse event IDs or change the meaning
of existing fields. Incompatible formats require a new schema and compatible
reader/release plan. The catalogue is product code, never customer-supplied
configuration.

The shared exception recorder also retains Python's visible explicit cause or
unsuppressed context chain, up to nine exceptions. Each `runtime.failure-cause`
records its bounded depth, link kind, closed exception and OS-error categories,
reviewed shipped-module location, and bounded subprocess exit status when the
exception is `CalledProcessError`. `256` means no reviewed subprocess status.
`runtime.failure-chain` distinguishes a complete chain from a cycle or depth
limit; the deepest retained exception is not necessarily the original cause
when that limit applies. Suppressed context, exception text, arguments, filenames,
subprocess output and traceback locals are never inspected. Existing
`runtime.fault` records retain their original top-level meaning.
Provenance collection is best effort: metadata or logging failures cannot
replace the original exception or prevent rollback. A fieldless
`runtime.failure-unavailable` marker reports incomplete provenance when the
logging sink remains usable; a broken sink cannot guarantee any new record.

Backend and rollback failures record this provenance before D-Bus error
delivery, including kiosk requests, child requests and session preparation
workers. Unexpected worker failures use the same recorder. Normal access denials,
busy responses, rate limits and invalid input retain their ordinary diagnostics.
Approval, policy-save, session-preparation, revocation and screen-time-toggle
transactions preserve the primary error before rollback can replace it;
execution-policy activation/removal retain primary and rollback failures too.
Background policy reconciliation, grant observation, startup runtime-cap cleanup
and diagnostic collection use the same recorder. Operation scopes distinguish
background attempts without introducing account or process references.

Feedback collection also observes the fixed runtime dependencies fapolicyd,
AccountsService, Polkit and logind through one read-only systemd query. Closed
load/active/result/restart categories, exit kind/status and restart counts
distinguish missing or failed services from application command failures. This
observation runs in diagnostics-only mode too. It does not restart a service or
acknowledge the daemon's active policy generation. A shared five-second budget
bounds this query and the fapolicyd journal read.
Both command pipes share a 256 KiB limit enforced while reading; timeout and
overflow paths reap the collector's own command. Service-query failure does
not suppress the independent journal read within the remaining budget.

The collector transiently reads at most 200 reviewed fapolicyd journal entries
from this boot's last 24 hours, selects only the fixed daemon executable under
`/usr/sbin` or the merged `/usr/bin` layout, and
retains at most 20 exact reviewed trust-update markers. It distinguishes the
observed service invocation from earlier attempts without retaining identifiers,
so recovery does not erase the earlier failure. When current invocation state
is unavailable, reviewed journal markers remain available with an `other`
invocation relation and partial evidence. Earlier-attempt evidence does
not alone establish causation for a later request. Only
closed reasons, the daemon's bounded diagnostic code and the original UTC event
time survive. No raw journal, output, path, invocation ID, PID or account field
becomes an attachment. Failed, malformed or saturated reads report unavailable
or partial evidence; a completed bounded query does not prove complete history.
In fapolicyd 1.3.6, `Cannot delete database (1)` identifies failure to start an
LMDB write transaction, but discards its original LMDB status. The report states
that limit explicitly; it must not infer a particular mutex, permission or
capacity cause from code 1 alone. Historical errors are not reconstructed when
their journal entries are unavailable.

Rule-notification failures separately classify exact C-locale CLI markers for a
missing endpoint, permission denial or an absent reader. Other output remains
`other`. These categories and service observations retain the original failure
and rollback behavior, and generalize to approval, policy-save, revocation,
session reconciliation and package-removal rule reloads. The additive catalogue
must ship with all validators; the collector activates on broker restart and
frontends load it on their next launch. No portal or saved-data change is needed.

Blocked-app operation failures record a fixed phase (preflight, running query,
identity, Flatpak termination, desktop application identity or native termination)
before the broker converts the failure into its public error. The original
exception and its bounded explicit cause chain supply only shipped-module
categories and source line numbers; the deepest retained cause supplies a closed
exception class and reviewed OS-error category. Flatpak `ps` and `kill` record
bounded subprocess exit statuses, including negative signal codes; `256` means
an unavailable or out-of-range status. No process/account identifiers, command
arguments, stdout/stderr, exception text or traceback locals enter these events.
Flatpak termination also records fixed discovery, termination and verification
stages, followed by counts of selected and still-matching instances. This
distinguishes a completed kill command with remaining instances from a failed
post-kill query or a later native discovery failure. It does not identify any
instance or prove that a successful command completed process exit.
These observations preserve failure and rollback behavior. Ship the additive
catalogue with all validators; the broker loads the diagnostics on process restart
and frontend validators load them on their next launch. A retained incident
captured before these producers were installed does not gain missing provenance
from a later installation; logs-only sufficiency needs a fresh instrumented
reproduction compared with independently established cause evidence.
No saved-data migration
or portal change is required.

### Investigation coverage

Child failures emit `child.failure` before launching the reporting window,
including failures received while that window is already open. Call sites own
closed operation labels for startup, language, reminders, Wellbeing, countdown,
session preparation/locking and request/report subprocesses. Only built-in
exception types and reviewed Gio/broker error categories leave the extension;
messages, stacks, paths, arbitrary remote names and request arguments do not.
The reporting window's separate empty `RuntimeError` is a placeholder, not the
original child exception. `child.process-exit` distinguishes an abnormal request
or reporter exit from a successful wait/communication; it records only the fixed
process role, exit/signal kind and bounded code (256 means unavailable). Owned
shutdown does not report its deliberately stopped process as a new failure.

`child.resume-refresh-failed` identifies queueing, usage query, record selection,
usage replay, estimate query or estimate processing, with the fixed error
category, observed native activity/limit booleans, consecutive failure count and
retry decision/delay. It adds no query or usage write and preserves cancellation,
backoff and the prohibition on late active-use replays. No usage intervals, UID,
native deadline or record contents enter diagnostics. Existing session
observations supply sleep/wake and lock context independently.

Python cause-chain recording adds `runtime.failure-gio` at each recognized
Gio cause depth, distinguishing transport failures and explicit broker refusals
such as reboot-required or backend-failure. Parent broker calls also record the
reviewed method name without arguments. GTK exception hooks retain original and
coalesced worker/callback failures before UI delivery, plus failures in error
presentation and its fallback. Kiosk authentication-agent preparation records
the failed stage and reviewed systemd job result, including speculative warm-up
failures; environment values, languages and job identities remain excluded.
These observations preserve existing error/retry behavior. The additive
catalogue ships with all validators; broker restart, child session renewal and
frontend relaunch load the respective changes. No saved-data migration is needed.

`kiosk.logout-fallback` records the failed session-manager handoff stage, fixed
failure/unavailable/timeout outcome and whether exit was requested. It separates
idle registration from an exit attempt and distinguishes registration, logout,
end-session acknowledgement and the existing 750 ms deadline. Exception paths
retain the ordinary privacy-safe Python cause/Gio details. It records no client
path, application/session identity or response payload, opens no new error UI,
and does not claim that the fallback returned the display to the sign-in screen.
Closed helpers ignore late replies and do not emit a new deadline failure.

`kiosk-selection-store.failure` distinguishes local-selector read, JSON decode,
directory creation, temporary write and atomic replacement failures. It retains
only the reviewed exception type and OS error category, including permission,
storage exhaustion, read-only storage and directory/file shape mismatches.
Missing files remain ordinary first-run state. No remembered UID, selector-file
path, JSON content or temporary filename enters diagnostics; the existing
nonfatal in-memory fallback and persistence/cleanup behavior are unchanged.

The child records anonymous logical display dimensions, geometry scale, Shell
theme scale and text scale at extension startup and display configuration changes.
Every feedback diagnostic collection independently queries the requesting
frontend's current session through Mutter's public `GetCurrentState` interface.
Active physical mode dimensions, configured scale, primary-display boolean and
current text scale are recorded in diagnostic events and in the attached
`system-info.json` display section. These values are collected afresh, not cached
from startup or a prior banner; automatic transport retries retain the already
collected submission snapshot. The query does not start a compositor and has a
two-second timeout. Unavailable display collection is explicit and does not
prevent other diagnostics. Only bounded numbers, booleans and collection status
survive projection; connector names, vendor/product/serial information, mode IDs,
positions and screen contents are discarded. Old reports without this additive
section remain readable. Ship the catalogue and validators together; broker
restart and child session renewal load events, and the next frontend launch loads
fresh feedback collection. The portal attachment contract needs no change.

Reminder diagnostics separate loaded configuration, threshold crossing and
banner actor state. `child.reminder-settings` records only list count and the
fullscreen boolean; `child.reminder-trigger` records duration operands and
critical urgency. `child.reminder-presentation` records changes to the owned
actor's visible/mapped flags, selected monitor's fullscreen flag, urgency,
compositor-inhibition ownership and disposal. Repeated unchanged state is not
logged. These are lifecycle observations, not proof that a physical monitor
displayed the banner. No reminder IDs, custom text, application/window identity,
monitor identifiers or screen contents enter the events. The additive catalogue
must ship with the child and broker validators; broker restart and child session
renewal load it. Older reports cannot reconstruct missing reminder events.

While the shared product reboot detector finds an installation or upgrade
request (see [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle)), the broker starts in
diagnostics-only mode. The existing role checks still authorize `LogEvent` and
`ExportDiagnosticLogs`, including the export's second check before delivery.
The service reads retained structured history and accepts new frontend events,
without constructing enforcement adapters, reconciling policy, changing child
sessions or starting policy/grant observers. The kiosk-only `ListKioskUsers`
and `GetChildLanguageContext` read endpoints also retain their role/target checks
so the restart notice follows the selected child's language. The read-only
preference store is composed without enforcement dependencies or writes.
All other methods, including the
startup-timing witness, return `Error.RebootRequired`; bus-name ownership alone
must not be interpreted as policy readiness. Migration exclusion remains intact.

The fieldless `service.diagnostics-only` event explains that product installation
or upgrade requires reboot and that policy operations
remain unavailable. It is recorded at diagnostic registration, rejected policy
calls and collection. Its source is the shared product reboot detector, never
journal text, an account, a path supplied by a caller or an exception message.
It makes this activation outage explainable from a customer archive. No historical
failure time is invented for older logs whose broker was stopped. This route
does not recover exports from unrelated broker import failures or incomplete
saved-data migration. Ship the launcher, unit, service and additive catalogue
together; their activation is `process-restart`, with frontend catalogue readers
renewed on launch. No saved-data migration or portal change is required.

Parent records `parent.startup-check` before and after its broker permission
check, with bounded monotonic wait duration and a closed outcome: ready, access
denied, reboot required or unavailable. Only exact broker error identities select
the specific outcomes; arbitrary D-Bus names and exception text are excluded.
Together with the broker's restriction event, this separates a launch waiting
on activation from an authorized management window. Records whose delivery
failed while the old broker was absent cannot be reconstructed retroactively.

The broker records dispatch outcomes, authorization and cancellation categories,
grant arithmetic, write/readback verification, revocation, rollback, extension
activation, execution-policy reconciliation, application termination counts,
preference persistence, startup timings, migration, and uninstall outcomes.
Parent, child, and kiosk events record displayed calculation inputs, request
and countdown transitions, session preparation, UI/resource failures, editor
lifecycle, and feedback collection/delivery/retry outcomes.

Account discovery records which AccountsService identity check failed:
`adapters.account-object-mismatch` distinguishes a `FindUserById` object-path
mismatch from a `GetAll` UID-property mismatch. Enumeration failures distinguish
NSS enumeration from account lookup. A transient comparison with the fixed
`gdm-greeter` service-account name supplies only the closed
`display-manager-greeter` role; all other candidates are `other`. Skipped
unavailable accounts are recorded without claiming that they were deleted.
Unexpected D-Bus dispatch failures also retain the reviewed shipped module
category and source line before conversion to the generic public error.
These events share the dispatch's local operation number, so a report can link
the failed list method, identity invariant, candidate role and failure location.
After a rejected `FindUserById`, a best-effort, one-second `GetAll` read records
`adapters.account-object-context`: numeric object-path shape, whether its UID
property matches the request and object path, and the returned account's closed
greeter role. Matching greeter roles with contradictory UID relationships point
to stale greeter identity metadata. This subsequent read is not an atomic
snapshot; failures leave comparisons unknown and retain the original rejection.
No names, UIDs, returned object paths, account properties, NSS rows or exception
text enter the events. `adapters.greeter-candidates-excluded` records that
discovery excluded candidates in the reserved dynamic-greeter UID range before
AccountsService lookup; it has no identity fields. Ordinary-account failures
and all direct identity checks retain their rejection and diagnostic behavior.
The broker loads these additions after `process-restart`; ship the additive
catalogue with all frontend validators, and renew frontend processes before
reading reports containing the new events. No saved-data migration is required.
Privacy, failure-preservation and readable export checks live in
[diagnostic privacy](../../tests/unit/test_diagnostic_privacy.py).

The shared request form records valid duration snapshots when preferences are
restored, form choices are edited, and a request is submitted. Each
`kiosk.duration-selection` includes only a fixed stage, preset/custom/rest-of-day
kind, validated seconds and the overlay flag. Form edits include changes to
other choices; an edited snapshot does not itself mean the duration changed.
Each snapshot has a fresh local diagnostic operation number so rapid duration
reversions survive identical-event suppression. Invalid custom text, account
identities, labels and unused custom values are never logged.
`kiosk.estimate-calculated` records daily, previous-grant, additional and total
seconds at INFO after rejecting stale replies. This is the frontend's accepted
estimate, not evidence that authentication completed or that the footer was
visible over a higher-priority status. Broker grant-calculation and verified
write events remain authoritative for approval. These events help distinguish
a restored custom duration from an edit and from time added by grant arithmetic;
they do not establish which controls a person saw or intended to select.

The new catalogue entries preserve existing events and stored reports. Ship the
catalogue and frontend together. The kiosk payload is classified as
`session-renewal`, which also restarts the broker to load its catalogue reader;
new request-form processes load the frontend changes. No saved-data migration
is needed. Selection, stale-reply, storage suppression and call-site privacy
regressions are covered in
[request selections](../../tests/unit/test_request_selections.py),
[request estimates](../../tests/unit/test_request_time_estimate.py), and the
catalogue-wide privacy checks.

[grant_diagnostics.py](../../broker/oh_no_parent_control/grant_diagnostics.py)
observes live grants after supported AccountsService change signals and bounded
periodic reconciliation. New `grant.observed-timed` events identify `source=our-app`
after a broker write and matching read-back, including clears and rollback writes.
`source=external` means a changed value against a retained baseline with no
unresolved app write. `source=unknown` covers the first observation (including
after restart or bounded-cache eviction), ambiguous write failures, and a mismatch
against a pending verified value. Attempts are marked before sending D-Bus writes;
a timeout can have applied the write, so it must not produce an external claim.
A verified write establishes a new known baseline; repeat unchanged reads are
suppressed, while verified app writes are recorded even when they are no-ops.
Events include the local observation timestamp, previous/new remaining durations,
and a boolean for expiry at local midnight. The observer compares absolute
second-resolution expiry with the next local midnight, avoiding fractional
second rounding mismatches against the integer grant representation.
An external increase expiring at midnight also emits `grant.external-rest-of-day`,
explicitly describing the observed rest-of-day grant and that the click and
authentication were not observed. Initial, ambiguous, and verified app writes
do not emit that external summary. Identity and raw grant timestamps
remain only in a bounded runtime lookup and never enter an event. Background reads never hold
the approval lock; a transaction revision discards observations that overlap
an in-flight or newly completed grant transaction. Wall/monotonic divergence is recorded as a
direction and bounded duration; suspension can also cause divergence.

External means outside the observed app writes, not a named actor or proof that
the login screen's Ignore button was clicked. This is state observation, not a
complete audit of every intermediate write: same-value writes and changes between
reads cannot be distinguished. With no identity tracking, reports cannot link unrelated
operations to a particular child. Missing or rotated observations cannot prove
that no grant occurred. The report explicitly distinguishes frontend
observations from broker decisions. This preserves useful arithmetic evidence
without turning diagnostics into an account activity history.

The earlier `grant.observed` catalog entry remains readable for retained logs;
its historical `unattributed` label is not upgraded to `external`. No saved-data
migration is needed. Broker changes activate at `process-restart`; frontend
catalog readers load on their next launch. Regression coverage is in
[diagnostic privacy](../../tests/unit/test_diagnostic_privacy.py) and
[log storage/export](../../tests/unit/test_logs.py). These checks do not qualify
the live login-screen flow.

## Feedback and diagnostic export

The Parent App exposes ordinary Send Feedback; Parent, Child and Kiosk App
errors use the same dialog for editable error reports. Submission runs in an
unprivileged frontend worker directly to
`https://tech.puffyslippers.com/api/oh-no-parent-control/feedback`. It sends
plain text, optional semantic HTML, optional reply email, app version,
user-selected attachment basenames and bytes, and an optional diagnostic ZIP.
The transport disables ambient credentials/proxy settings and redirects; it
does not send local attachment paths, private preferences, or provider secrets.
Use this disclosure consistently in the Parent App, website, and portal
operations guide:

> Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support. Retention depends on our support mailbox and service providers, including their backup policies. We do not currently guarantee deletion within a fixed period.

The feedback footer provides a Privacy link that opens the disclosure and
diagnostic-log explanation. In the dedicated kiosk session the privacy dialog
omits its external link, and feedback hides log download, Add files, and the
editor's attachment shortcut. The in-session request overlay is Child App and
retains those controls. File chooser entry points enforce the same restriction.
The footer stays outside the form's scrolling area so Close and Send remain
visible on short displays, including when all five file attachments or a long
status message are shown. The rich-text editor continues to scroll its own text;
its formatting dropdown scrolls within the editor viewport when space is tight.
User-file rows expose their name, size and Remove action. Their attachment icon
has an accessible label stating that preview is unavailable; they do not open a
preview. This label activates in newly launched frontends and changes no saved data.

### Error reports

[errors.py](../../common/oh_no_parent_control_ui/errors.py) creates a fixed public
title/explanation and at most eight closed exception categories. Caller-provided
error explanations and exception messages, including causes, never enter the
automatic draft or diagnostics. Customers can edit and add their own text to
the bounded plain-text draft. The subject is
`[Oh No! Parent Control] [Component] Error Report`, with Component restricted to
`Kiosk App`, `Child App`, or `Parent App`.

The shared request error screen provides a default-on **Report this error**
switch using the request form's toggle style. Return to Login, Close, and
Escape review the report when enabled, then leave after feedback is closed.
Turning it off leaves directly. Successful requests never offer error reporting.
Other operation failures and uncaught Python callbacks/workers open feedback
through the same handler. Parent startup failures show a reporting-only window,
except for an explicit broker management-access refusal, which shows the
[administrator-access notice](Frontends.md#parent-controls-and-shared-information).
Neither exposes management controls. Repeated failures preserve the active
draft. Input validation and cancelled authorization remain normal form states.

The child Shell extension's [errorHandler.js](../../child/errorHandler.js)
forwards timer, session preparation, locking, and request-launch failures to
the same Child App reporter using a fixed failure marker over a private
subprocess stdin pipe. Exception contents never enter the pipe or arguments.
Only its retained subprocess may be stopped
when the extension is disabled.

The shared dialog selects error-report presentation when supplied an `ErrorReport`:
**Report an Error**, a pink warning icon, **Sorry about the inconvenience**, and
**Something went wrong. Help us fix it by sending a report.** Its empty-editor
watermark asks what the user was doing and invites details to reproduce and fix
the issue, including after deleting the text from a heading, list, quote or code
block. The watermark is separate from the draft and preserves the selected
formatting. The editable public explanation remains the initial draft.

Opening a report sends nothing. **Send Error Report** is explicit. While an error report
is sending, its Close action becomes **Stop sending and close**, which cancels
pending retries before leaving. A request already accepted remotely cannot be
recalled. Ordinary feedback retains its existing background retry behavior.
All three apps request the same validated diagnostic report from the broker's
`ExportDiagnosticLogs` method. The broker validates the caller as a local
administrator, configured kiosk, or eligible child before collecting and again
before replying. This deliberately permits those roles to review all four
components' generated events; filesystem permissions remain unchanged.
No saved preferences change. Shared assets install under `common/oh_no_parent_control_ui`;
the request and Shell payloads retain `session-renewal` activation, and new app
processes load the shared dialog.

Server-side sanitization, email
routing, and retention enforcement belong to the separately deployed endpoint.

The editor is locally bundled Quill 2.0.3 inside an ephemeral WebKitGTK 6 web
view. The in-memory page's content-security policy denies network sources and
navigation away from the editor is blocked. Editor content crosses the local
message bridge as plain text, semantic HTML, and a Quill delta used to restore
the draft after a web-process restart.

Combined underline and strikethrough use explicit decoration styling on the
nested editor elements, including links inside struck text. This preserves both
visual decorations and exposes both
through public accessibility text attributes; removing either format removes
its attribute too. Semantic HTML and the submission contract are unchanged.

The editor exposes heading levels, numbered/bulleted list-item descriptions,
quotations and code blocks to assistive technology. These semantics follow the
formatted content after edits, removal, undo/redo and delta restoration, without
changing the editor root role or Quill document model. New frontend processes
load this accessibility change; no saved-data migration is required.

Local Send validation rejects NUL (`U+0000`) and SOH (`U+0001`) in the plain-text
body with the unsupported-hidden-character explanation, before creating a
submission. Normal tabs, newlines and emoji remain supported within the existing
UTF-16 limits. New frontend processes load this validation change; no saved-data
migration or portal change is required.

Ordinary Parent feedback drafts, selected file bytes, and frozen retries remain
in memory until app exit; closing that dialog preserves them and allows an
in-flight worker to continue. Error reports have an exit callback instead:
closing them ends that report, cancels pending sending and destroys the dialog.
Repeated errors while a report is open preserve the active edited draft.
Successful sending clears the draft and, while feedback is visible, immediately
hides the feedback window and opens a modal thank-you confirmation on its owning
window. The confirmation stays open until the user dismisses it with **Close**
or another manual dismissal action; there is no countdown. When the submitted
report includes a reply email, it adds a note that support may contact the user
with follow-up questions. Error-report close callbacks run only after the
confirmation is dismissed. Background
completion does not reopen feedback that the user already closed.
Parent and child-overlay feedback can explicitly save a diagnostic ZIP to a
chosen location; the dedicated kiosk cannot open that file chooser.
The broker's [collector](../../broker/oh_no_parent_control/diagnostics.py)
reads only regular structured event files from each component's three newest
available UTC source-file dates (not necessarily consecutive calendar days), rejects symlinks and hard
links, and limits input to 16 MiB, records to 12,000, and the ZIP to 2 MiB. The export method accepts no
path, UID, date, or component selector. Collection runs off the dispatch thread,
with one outstanding export through reply delivery. Collection errors expose
only a generic error; diagnostic records contain categories and byte counts.
The shared [client](../../common/oh_no_parent_control_ui/diagnostics.py) uses
this method for both feedback and downloads, including from child accounts.
The transport separately caps an attached log ZIP at 2 MiB,
user attachments at five files of at most 5 MiB each, and all attachments plus
logs at 8 MiB. Collection or size failures allow sending without diagnostics.
Attachment selection reads all chosen files before adding that batch; an
unreadable, invalid-name or oversized member rejects the whole new batch while
preserving existing attachments. Names are normalized to basenames, limited
to 180 characters and checked for Unicode control/format characters. Selected
bytes are held in memory from that point, so later source-file edits do not
alter a draft attachment. The diagnostic download uses the cached snapshot;
cancel or save failure retains it. **Send without logs** removes the diagnostic
attachment and immediately attempts the ordinary validated Send action.

The schema-3 archive contains `system-info.json` and the four component folders,
with readable `<component>/YYYY-MM-DD.log` files for each component's three
newest available source dates. Empty component folders remain visible; the
summary's `logs` mapping lists retained files and exported record counts. Source
rotations and incident copies are merged and deduplicated. Normal source files
establish dates when an incident repeats an earlier record; incident-only
context can include earlier observations, as each log's header explains. Dates
come from validated source filenames, never a customer-provided path. No date
or history is invented for an inactive component. Input and attachment limits
can still trim records; collection counters report that loss.

[diagnostic_report.py](../../common/oh_no_parent_control_ui/diagnostic_report.py)
renders and parses a fixed log grammar. Each line retains severity, diagnostic
segment, elapsed offset, sequence, operation, event ID, closed fields, and the
catalogue's readable description. The validator reconstructs every line and
rejects altered prose, private fields, unexpected paths/files, extra directory
contents, duplicate ZIP members, or mismatched record counts. There is no
separate `events.jsonl`, `manifest.json`, or duplicate `report.txt` in new exports.
ZIP timestamps are fixed. ZIP comments, extra metadata, and trailing bytes are
discarded by rebuilding before transmission.

`system-info.json` combines `health`, collection `counts`, the `logs` inventory,
and a `system` object. The broker leaves `system` null; the frontend fills it
before offering the same snapshot for download or submission. Health includes
fixed liveness states for AccountsService, the timer,
Polkit, and systemd, plus migration and last diagnostic-write states. A bus-name owner indicates
liveness, not complete service health; probe failure is `unknown`. Collection
starts when feedback becomes visible, with no background upload. Download and
Send use the same prepared snapshot.

### System information and collection state

[system_info.py](../../common/oh_no_parent_control_ui/system_info.py) collects
OS distribution/version, the running frontend's app version, numeric kernel
version, architecture, effective user timezone/UTC offset, session type, runtime
dependencies, and aggregate account counts. Optional-source failures are explicit
`partial`, `unavailable`, or `unknown` states. They never become raw error text or
silently imply complete collection. Service liveness and diagnostic-storage
information live alongside the system fields in the same compact summary.

[diagnostic_privacy.py](../../common/oh_no_parent_control_ui/diagnostic_privacy.py)
projects only reviewed fields. It retains bounded numeric upstream version
components, dropping epochs, packaging revisions and all custom suffixes.
Support must not infer an exact distro package revision from this value.
OS/session/architecture categories and dependency names are closed lists.
New reports include only named, reviewed runtime dependencies. Older inventories
are projected onto that same list before inclusion; their anonymous
`[Dependency]` rows are omitted. Dependencies have no numbered labels. There are
no hashes, encrypted identities, mapping files, or cross-report identity references.
Raw OS branding, environment values, package origins, paths and exceptions are
never serialized. The timezone-name allowlist is shipped in
[diagnostic_timezones.json](../../common/oh_no_parent_control_ui/diagnostic_timezones.json),
derived from the public-domain IANA tzdata 2026c zone/link names. Custom timezone
names become `unknown`; the numeric offset still describes the frontend's
effective timezone. The root broker's timezone is not used as the user's zone.

The read-only, in-memory Python APT cache looks up exactly 20 named packages:
AccountsService, fapolicyd, GDM, GNOME Kiosk/Shell, GJS, malcontent, Polkit,
systemd, D-Bus, GLib, GTK, libadwaita, WebKitGTK, libmalcontent, the malcontent
PAM module, Python, and its APT/GI/requests bindings. The fixed
`DIAGNOSTIC_PACKAGES` list is the collection scope; no dependency traversal,
provider enumeration, or general installed-software inventory is performed.
Missing packages are explicit and mark collection partial; a ten-second lookup
budget remains. Quill adds one bundled version, regression-checked against its
shipped notice. OS/kernel, app version, architecture, timezone/session type and
account counts remain available. `python3-apt` is declared in
runtime/build dependencies; existing `setup.sh --dependencies-only` installs build
prerequisites through its existing build-dependency route. No new setup entry
point or privileged runtime command is introduced.

Package collection selects available Python APT bindings, falling back to RPM
when those bindings are absent, independently of the OS identity category.
The RPM collector uses one read-only query for its fixed
20-package runtime list, including dconf. Only named packages' numeric upstream
versions and reviewed architecture categories survive projection. Epochs,
release revisions, origins, query stderr and arbitrary metadata are excluded.
The same ten-second budget applies; missing packages mark collection partial,
and a failed or malformed query marks it unavailable. Export preserves these
reviewed RPM rows alongside the existing APT rows. Unreviewed distro identities
remain `unknown` without preventing package collection. Unsupported package
backends report `unavailable`; distro-specific package names absent from the
fixed list report `partial`. Fedora remains a reviewed OS category. New frontend processes load this change; no saved
data, package dependency or portal change is required.

Account collection reads a bounded local passwd file transiently to enumerate
local interactive candidates, then requests only AccountsService `LocalAccount`,
`SystemAccount`, and `AccountType` properties. Names/home paths are never emitted;
the shared helper receives only role categories and produces counts. Root,
system/service accounts, and the reserved product kiosk account are excluded.
Remote/NSS-directory identities are outside this local-account scope. Failed
lookups and the five-second account-read budget mark the counts partial.

The broker also adds `user_languages` to `system-info.json`, with one saved
personal language selection per local interactive parent (administrator) and
child (non-administrator). Root, system, remote and configured kiosk accounts
are excluded; locked human accounts remain included. Generic `[Parent 1]` and
`[Child 1]` labels are assigned after sorting only role and projected language,
never account names, UIDs or discovery order. They have no retained identity map
and cannot correlate an account with events or another report. Only exact
shipped catalogue IDs survive; empty preferences become `unset`, unreviewed
values become `other`, and failed preference reads become `unavailable` with a
`partial` collection status. No desktop/session language is inferred for an
unset selection. Enumeration failure reports `unavailable`; the broker reuses
the bounded local account-role reader instead of general NSS account discovery.
Failed role lookups mark the report `partial`. Collection stops at 256 users or
its shared five-second account/preference-read budget and reports `partial`.
The broker reuses diagnostic-export authorization and reads preferences without
changing them, including in diagnostics-only mode. Frontend enrichment and
submission revalidate and preserve these fields. Older reports without the
optional field remain accepted; older frontend validators need restarting onto
the matching package before collecting the expanded report. This loads with
broker process restart and new frontend processes; no saved-data migration or
portal API change is required.

Opening feedback displays a spinner and **Collecting diagnostic information...**.
The shared dialog uses `Adw.Spinner`, whose animation follows row visibility and
continues with desktop animations disabled; `Gtk.Spinner` freezes in that mode.
The parent feedback UI regression compares eight rendered frames with animations
enabled and disabled, alongside the collection/editing lifecycle assertions.
Send is disabled while collection is pending; editing and Close remain available.
Success restores the attachment row and enables Send. Failure stops the spinner
and offers Retry collection or explicit sending without diagnostics. A separate
collection state preserves submission/retry semantics: opening during an active
submission never changes its frozen bytes. Reopening during collection shares
the one outstanding worker; a later opening refreshes the snapshot. Completion
never reopens a hidden dialog, and destroyed dialogs ignore late completions.
All three frontends use this shared behavior and retain kiosk file restrictions.

The new frontend accepts schema-3 broker snapshots and adds system information
locally. It also accepts previous structured schema-1/2 snapshots, converting
their events to `<component>/undated.log` because those formats discarded source
dates. It never assigns today's date to older events. The transport validates
all three schemas and strips ZIP metadata. The broker D-Bus signature is
unchanged; older frontend validators reject schema 3 and need restarting onto
the matching package. New frontend processes load these
changes; child/shared kiosk activation remains `session-renewal`. No saved-data
migration or portal change is required.

Regression coverage: [dated reports and archive privacy](../../tests/unit/test_diagnostic_report.py),
[per-component date selection](../../tests/unit/test_diagnostics.py),
[system-info privacy and bounded lookups](../../tests/unit/test_system_info.py),
[collection lifecycle](../../tests/unit/test_feedback_collection.py), and shared
[Parent](../../tests/ui/test_parent_feedback.py)/[Child and Kiosk](../../tests/ui/test_error_feedback.py)
feedback UI checks. These are local collector/component checks, not qualification
of installed VM collection or remote delivery.

The additive D-Bus contract and broker collector activate with `process-restart`.
New app processes load the updated export client; kiosk/shared request payloads
and child catalogue retain `session-renewal`. Ship the broker and frontends
together. A new client rejects raw archives from an older broker and preserves
the draft for sending without diagnostics. Old frontend text log payloads are
rejected by the new broker until those processes are restarted. The additive,
role-checked `GetStartupTimings` method supplies supported read-only timing
evidence to lifecycle tests; tests retain their live bus-owner/process continuity
checks instead of finding identifying startup witnesses in logs. Those test
identity observations never enter feedback reports. There is no portal contract
or saved-application-data migration for this format change.

## Multipart and retry contract

The generic portal contract accepts `title`, `body`, optional `bodyHtml` and
`replyTo`, and repeated `attachments` file parts. The client composes the entire
email, including branding, version, receipt, attachment counts, and error
details. It chooses the title, using the three component subjects above for
error reports and `[Oh No! Parent Control] App feedback` for ordinary feedback.
The diagnostic ZIP is an ordinary attachment named by the client; the portal
has no special log field, component list, or report template. It validates
delivery limits, sanitizes HTML and attachment basenames, and forwards the
client's content to its configured support mailbox. Future report formats
change in the client without changing this API.

Client sending is enabled (`SENDING_ENABLED = True`). The matching generic
portal handler is a release dependency; this checkout cannot establish its
current deployed behavior, and older handlers reject these multipart fields.
A frozen submission retains
all content and one `Idempotency-Key`
through a bounded 15-minute retry window, with a 30-second request timeout.
Each explicit Send action creates a new submission identity; automatic retries
reuse the frozen report and key.

A JSON `202` response with `ok: true` confirms success and may include a
`receiptId`. Network failures, server errors, `408`, and unconfirmed `202`
responses retry with bounded backoff; `429` also respects the bounded
`Retry-After` delay. `409` ends the expired submission and `413` reports size
failure. No persistent queue is created. See `feedback_transport.py` for exact
validation bounds and response handling.

## Related design

- For D-Bus log authorization, read [Broker](Broker.md#broker-interface-and-roles).
- For retention across remove versus purge, read [Package removal](Package-Removal.md#remove-purge-and-retry).
