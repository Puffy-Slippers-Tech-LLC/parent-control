# Logging, diagnostics, and feedback

[System design overview](../System-Design.md)

Automatic diagnostics exclude personal information. Customer-written feedback,
reply email and explicitly selected attachments remain separate voluntary inputs.

Implementation: [log storage](../../broker/oh_no_parent_control/logs.py),
[broker collector](../../broker/oh_no_parent_control/diagnostics.py),
[diagnostic catalogue](../../common/oh_no_parent_control_ui/diagnostic_catalog.json),
[feedback](../../common/oh_no_parent_control_ui/feedback.py),
[transport](../../common/oh_no_parent_control_ui/feedback_transport.py),
[editor](../../common/oh_no_parent_control_ui/rich_text_editor.py).

## Logging

The broker alone writes structured events to
`/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.events`.
Directories are `0750`, files `0640`, owned by `root:sudo`.
Frontends submit role-scoped `LogEvent` envelopes; broker events are internal.
Human-readable runtime-helper prefixes use `onpc.<domain>`.

Each component retains three available UTC dates with three 256 KiB segments
per date. Identical events within 60 seconds are suppressed/counted.
Routine countdown observations are sampled, retaining increases/zero transitions.
An error, invalid grant, clock divergence or unattributed increase pins the
preceding 40 records per component into the bounded latest incident; error
context has priority when trimming. Counters expose suppression, loss, rotation,
invalid input and write/storage failures.

Timing events retain bounded elapsed durations, never raw clocks, frame counters
or identities. Form completion requires loaded settings/accounts/language,
settled estimates/transitions, the request page and no owned modal.
`form-painted` is not display visibility; `form-presented` requires actual
GDK feedback. The read-only same-UID `KioskTiming1` witness exposes engineering
monotonic timestamps (zero when unavailable), with bounded credential checks,
owner/process/boot binding and application-lifetime registration. Its failure
cannot block the UI; absolute timing evidence stays outside feedback.

Countdown diagnostics distinguish native/timer operands, accepted broker balance,
source changes and loaded/limit/lock/greeter states. They neither establish a
fresh native deadline nor attribute who locked a session. Logging adds no policy/
timer queries and cannot interrupt refresh or enforcement. Resume diagnostics
distinguish deferred transient reads/replays from permanent/exhausted failures;
healthy idle reads do not erase repeated active-stage failure evidence.
Identity-scoped usage-helper errors retain only reviewed categories.

### Native login and unlock observations

The child observer records changes in native limit decisions, logind activity/
idle/locked hints and Shell lock/greeter state, without causing those changes.
Only the current session proxy's current logind owner supplies Lock/Unlock
observations. A local ordinal distinguishes repeated Unlock requests; one owned
one-second timer records resulting state. New requests, Lock, suspend, owner
replacement or disposal retire it. Observation is not password-success proof.

Unlock continuation events distinguish arming, one native dispatch, observed
unlock, cancellation, failure and expiry. After dispatch, interruption/expiry
describes observation: the public native API cannot retract its pending callbacks.
Closed reasons, bounded elapsed/remaining durations and booleans exclude
credentials and all account/session/device identities.
[Screen time](Screen-Time.md#countdown-and-expiry-enforcement) owns authority.
Optional observation/diagnostic failure cannot change admission or enforcement.

### Event timestamps

New events include broker UTC observation time with millisecond precision and
`Z`; files/incident dates use UTC. Monotonic offsets preserve elapsed timing
across clock corrections. Older records/schema-3 reports lacking UTC timestamps
remain readable without invented times or rewriting stored logs.

Legacy raw logs are never imported, exported, modified or pruned by this pipeline.
Journals, subprocess output, preferences and app inventories are not attachments.

### Kiosk admission diagnostics

Native PAM and fixed login-helper journal/syslog markers diagnose authentication,
routing, repair, preparation and removal before the station starts. Stage success
does not prove usable entry; routing repair never converts that failed attempt
into an allowed login.

The [closed parser](../../broker/oh_no_parent_control/dependency_diagnostics.py)
requires exact reviewed formats and producer provenance. It runs independently
of a surviving manager or normal policy readiness, with a five-second read of
the last 24 hours across retained boots, at most 200 entries and 20 exported
markers. Clipping preserves the first denial and newest causal-phase witnesses,
then distinct/repeated failures before successes, keeping source chronology.
Recovery does not erase the original denial. Missing/rotated history cannot be
reconstructed or treated as complete.

Output contains source UTC time, closed producer/role/stage/outcome/reason and
session/transport/recovery categories, bounded status/errno/source line and
aggregate counts. Missing status/errno/line use -256/-1/0.
Observation is complete, partial or unavailable; rejected records, a full tail
or marker clipping make it partial. Root journal credentials, reviewed executable/
unit provenance and PAM-service role agreement are required. Spoofed/unknown
formats and fields are discarded.

Raw messages, names, UIDs, session/process/mount identities, paths, arguments,
metadata and exception text never leave projection. Local package-manager
compiler errors remain local engineering output. Cleanup failures retain
ownership/recovery state; diagnostics never authorize admission.

#### Retained historical admission formats

Readers retain exact older execution-boundary, confinement-preparation,
directory-view/entry and native-view schemas for compatibility. Their retired
producers do not require replacement private views, MAC roles or manager
generations. Old stale-material/generation-limit reboot reasons describe those
old refusals, not current reboot policy.

Historical native-view parsing preserves primary versus cleanup failures and
validates closed role/stage/reason values and numeric bounds. Measurement refusals
retain only reviewed fixed causes; unavailable/malformed cause packets preserve
ordinary refusal. A stale-material classification requires independently verified
current material and the original trusted manager/record/topology, never a generic
refusal. None of these records attests installed recovery.

### Kiosk startup crash diagnostics

Before export, independent bounded projection reads this boot's last 24 hours:
a shared five-second budget, at most 200 entries and 20 markers per source.
Each source reports complete/partial/unavailable for that bounded read.
Invalid kiosk identity prevents querying another account; no session/service/
renderer/policy changes occur.

Reviewed security/renderer/systemd markers distinguish GPU mapping denial, Vulkan
mapping failure, Mesa crash, numeric exit/signal and failure-triggered session
shutdown. Renderer records require configured kiosk identity and executable/unit
provenance; security records require trusted kernel/audit transport and exact
policy contexts. Transient PID correlation never becomes output.
Source chronology supports diagnosis without claiming unrelated denials caused
an exit. Raw identities, addresses, paths, stack traces and messages are discarded.

### Schema and field provenance

The shipped catalogue defines stable event IDs/text, components, exact fields,
closed enums, booleans and bounded numbers. Validate at production, storage,
export, frontend and HTTP transmission. Rebuild approved records rather than
passing through unknown data. Extra fields, legacy arbitrary payloads and text
fail closed; unknown enum inputs project to fixed `other`. Foreign Python logs
produce a suppressed marker without formatting arguments/exceptions.

Permitted fields include operation outcomes, counts, duration operands, product
versions, elapsed timings and fixed dependency states. Random per-request
references never derive from people/accounts/devices. Export renumbers local
diagnostic segments. Grant observations may include local observation time and
UTC offset; raw grant issuance and boot/session timestamps are excluded.

Forbidden sources include names, UIDs, email, attachment names/content, paths,
commands, environments, URLs, hosts, addresses, device/app identifiers,
credentials, exception messages and traceback locals. Hashes/stable pseudonyms
do not make them permissible. Bounded numeric types still require call-site
provenance review. New logging needs a catalogue entry, source review and privacy
coverage. Preserve event/field meanings; incompatible formats need a new schema
and compatible reader/release handling.

Exception provenance retains up to nine visible causes/unsuppressed contexts,
closed exception/OS/Gio categories, reviewed shipped-module/source-line locations
and bounded subprocess exit codes (256 means unavailable). Cycle/depth limits
are explicit; deepest retained need not be original. Suppressed context, text,
arguments, output, filenames and locals are never inspected. Best-effort
provenance cannot replace the primary error or prevent rollback.

Activation diagnostics retain fixed command/key/transport, configured/active
booleans, verification/rollback stages and classified C-locale warning markers.
A successful exit alone proves neither a started offline bus nor committed
settings. Netlink/SELinux daemon startup failures remain separate.
Read-only `GetExtensionInfo` and policy/trust probes share an eight-second
budget and catch import failures before extension logging exists.
Unknown tools/results stay unknown. Database/rule observations never acknowledge
the active daemon generation.

Dependency collection queries fixed systemd services and reviewed fapolicyd
journal markers under one five-second budget and 256 KiB pipe bound. Timeout/
overflow reaps only its owned command. Reads are independent within the budget,
retain at most 200 entries/20 markers and distinguish earlier invocation failures
without exporting invocation IDs. Earlier evidence alone does not explain a
later request. LMDB's `Cannot delete database (1)` loses its original status;
reports must not invent a mutex/permission/capacity cause. Rule-notification
markers distinguish endpoint, permissions and absent reader, otherwise `other`.

Blocked-app diagnostics distinguish preflight/query/identity/native/Flatpak
phases, subprocess outcomes and aggregate selected/still-matching counts.
Successful kill commands do not alone prove exit. Primary/rollback behavior is
unchanged; old incidents cannot acquire later instrumentation retroactively.

### Investigation coverage

Events cover authorization/cancellation, arithmetic, verified writes, rollback,
activation, enforcement/termination counts, persistence, migration/removal and
frontend request/editor/collection/delivery failures. Public error conversion
must not discard original privacy-safe provenance. Child reports carry a fixed
failure marker, not the original exception in subprocess arguments.

Child operation labels distinguish countdown, language, reminders, Wellbeing,
resume refresh, session preparation and owned process exits. Agent preparation,
logout handoff and selector storage retain closed stages/outcomes rather than
locale/job/path/UID values. Ordinary missing selector files remain first-run
state. Observer failure never changes native behavior.

Display collection uses fresh requesting-session Mutter state with a two-second
timeout: bounded physical/logical dimensions, scales, primary boolean and status.
No connectors, serials, positions, mode IDs or screen contents survive. Reminder
diagnostics distinguish configured thresholds, crossing and actor visibility/
mapping/fullscreen/inhibition state; actor state is not physical-display proof.

During a product installation/upgrade reboot guard, the broker runs diagnostics
only. Normal role checks authorize `LogEvent` and `ExportDiagnosticLogs`,
including recheck before delivery. Kiosk-only `ListKioskUsers` and
`GetChildLanguageContext` remain read-only so restart notices use child language.
No enforcement adapters, reconciliation, policy/grant observers or preference
writes are constructed. All other methods, including startup timing, return
`Error.RebootRequired`; bus ownership is not management readiness.
Migration exclusion still applies. The fieldless diagnostic identifies this
guard without inventing old failure times or recovering unrelated import failures.

Account discovery records object-path versus UID-property mismatch and fixed
greeter/other role categories. A bounded follow-up read supplies non-atomic
relationship context, preserving the original refusal; names, numeric UIDs and
paths remain excluded. Reserved dynamic-greeter exclusions carry no identity.
Request-duration snapshots log validated kind/seconds/stage with local operation
numbers; invalid text/unused custom values are excluded. Accepted frontend
estimates are distinct from approval decisions or what a person saw/intended.

Grant observation labels `our-app` only after a write and matching readback;
`external` requires a changed retained baseline with no unresolved app write.
First/ambiguous observations, cache eviction and mismatched pending writes are
`unknown`. Mark attempts before dispatch: timeout can mean the write applied.
Verified no-op app writes remain observations; unchanged background reads suppress.
A transaction revision rejects overlapping background observations.

External midnight-expiry increases describe observed rest-of-day grants, never
a particular login-screen click, authentication or actor. Remaining-duration
operands and local observation time do not expose identity/raw grant timestamps.
Same-value/intermediate writes and missing history are unknowable. Old
`unattributed` events remain readable and are not upgraded to external.

Catalogue and producers/validators must ship together. Broker readers load on
process restart, GTK readers on relaunch and child code on session renewal.

## Feedback and diagnostic export

Parent offers ordinary feedback; every role offers editable error reports.
An unprivileged worker sends explicitly to
`https://tech.puffyslippers.com/api/oh-no-parent-control/feedback`.
It sends plain text, optional semantic HTML/reply email, version, explicitly
selected basenames/bytes and an optional diagnostic ZIP. Ambient credentials,
proxy settings and redirects are disabled; local paths/preferences/secrets are
excluded.

Use this disclosure consistently across product, website and portal:

> Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support. Retention depends on our support mailbox and service providers, including their backup policies. We do not currently guarantee deletion within a fixed period.

Privacy explains diagnostics. Dedicated kiosk omits external links, file/log
choosers and attachment shortcuts, including indirect entry points; overlay
retains them. Footer Close/Send stay reachable outside scrolling content.
User-file rows expose basename/size/Remove and explicitly have no preview.

### Error reports

Fixed public titles/explanations and at most eight closed exception categories
seed drafts; supplied explanations and exception/cause messages never do.
Customers may edit the bounded draft. Subjects identify only Parent App,
Child App or Kiosk App. Input validation/cancelled approval remain normal states.

Request errors default reporting on; exit/Escape reviews the report then leaves,
or exits directly when disabled. Startup errors show reporting-only UI except
exact Parent management denial, which shows Administrator Required.
Repeated errors preserve an active edited draft. Opening sends nothing.

The local Quill 2.0.3 editor runs in ephemeral WebKitGTK 6 with network-denying
CSP and blocked navigation. Its bridge returns text, semantic HTML and a delta
for web-process restart restoration. Accessible formatting follows content,
including combined underline/strike, headings/lists/quotes/code and undo.
Reject NUL/SOH before submission; normal tabs/newlines/emoji remain valid within
existing UTF-16 limits.

Ordinary drafts, attachment bytes and retries live in process memory; closing
feedback preserves them and permits its worker to continue. Closing an error
report cancels pending retries and ends that report. Already accepted remote
delivery cannot be recalled. Successful visible submission clears the draft,
hides feedback and shows a manually dismissed thank-you modal; error exit waits
for its dismissal. Background completion never reopens hidden feedback.

All roles request the same four-component report through argument-free
`ExportDiagnosticLogs`. Role is checked before collection and before delivery;
one export remains outstanding through reply delivery. No arbitrary path, UID,
date or component selector exists. Collection is off the dispatch thread and
generic failures reveal no private data.

The collector accepts regular event files only, rejects symlinks/hard links and
bounds input to 16 MiB, records to 12,000 and ZIP to 2 MiB. Each component uses
its newest three available UTC source dates, not necessarily consecutive.
Rotations/incidents merge and deduplicate; source dates remain authoritative
even for older incident context. Missing history is never invented.

Schema 3 contains `system-info.json`, four component folders and readable
dated logs. Empty folders remain; retained counts match the log inventory.
The fixed grammar reconstructs severity, segment, elapsed/UTC time where present,
sequence, operation, event ID, fields and catalogue description. Reject modified
prose, unexpected/duplicate ZIP entries, paths or mismatched counts.
Rebuilding fixes ZIP timestamps and strips comments/extra metadata/trailing bytes.

Broker `system` is null; frontend adds reviewed system information before the
same snapshot is offered for download/Send. Health reports fixed liveness states
and storage/migration observations; bus ownership proves liveness only.

Transport allows five user files at most 5 MiB each, ZIP at most 2 MiB and
8 MiB combined. New selection batches are all-or-nothing; failure preserves
existing attachments. Basenames have at most 180 characters and reject control/
format characters. Bytes freeze at selection. Diagnostic download reuses the
snapshot; cancel/save failure retains it. Collection/size failure permits
explicit sending without diagnostics; Send without logs immediately attempts
the ordinary validated action.

### System information and collection state

Projection permits reviewed OS/version/kernel/architecture, effective frontend
timezone/offset, session type, runtime dependencies and aggregate local-account
counts. Numeric upstream package versions discard epochs/revisions/custom
suffixes; exact distro package revision is unknowable. Closed lists constrain
OS/dependency/architecture fields; timezone names use shipped IANA-derived
allowlist entries, otherwise unknown. No origins/raw branding/environment,
identity maps or encrypted/pseudonymous identifiers are serialized.

Fixed APT/RPM package lists use a ten-second read budget without dependency
traversal or general software inventory. APT bindings are preferred when
available, otherwise RPM; unsupported backends are unavailable, missing named
packages partial. Only reviewed package names/numeric versions survive.
The bundled editor version is separately included.

A bounded local-passwd/AccountsService reader counts interactive local roles,
excluding root/system/kiosk/remote identities, within five seconds.
Role lookup failure makes results partial. Optional saved user-language rows
include locked humans, sort by role/projected language and use generic numbered
Parent/Child labels without a retained identity map. Exact catalogue IDs,
unset/other/unavailable are the only values; no session language is inferred
for unset. Account/preference collection stops at 256 users/shared five seconds.

Collection starts when feedback becomes visible. A spinner keeps animating
even with desktop animations disabled. Pending collection disables Send while
editing/Close remain usable. Failures offer retry or explicit send without logs.
Reopening shares an active collection; later opening refreshes. Completion never
reopens hidden UI, disposed dialogs ignore replies, and an in-flight submission's
frozen bytes never change.

New frontends also accept structured schema 1/2 and convert them to undated logs,
never today's date. Raw archives/legacy text payloads are rejected. Older
validators need the matching package/process restart before reading expanded
reports. Ship broker/frontend validators together; no preference migration or
portal format-specific API is required.

## Multipart and retry contract

The generic endpoint accepts `title`, `body`, optional `bodyHtml`/`replyTo`
and repeated `attachments`. Client composes branding/version/receipt/counts
and component error subjects; ordinary subject is
`[Oh No! Parent Control] App feedback`. Diagnostic ZIP is an ordinary attachment.
Server validates limits, sanitizes HTML/basenames and routes to support; delivery
and retention belong to the separately deployed endpoint.

Sending is enabled; a matching deployed handler is a release dependency that
this checkout cannot establish. Each explicit Send creates one frozen content
snapshot and `Idempotency-Key`; automatic retries reuse it for at most 15 minutes,
with a 30-second request timeout and no persistent queue.

JSON `202` plus `ok: true` confirms success, optionally with a receipt.
Network/server/408/unconfirmed-202 failures retry with bounded backoff;
429 respects bounded Retry-After. 409 ends expired submission; 413 reports size.
Exact validation/response handling lives in the transport implementation.

## Related design

- [Broker permissions](Broker.md#broker-interface-and-roles).
- [Remove/purge retention](Package-Removal.md#remove-purge-and-retry).
