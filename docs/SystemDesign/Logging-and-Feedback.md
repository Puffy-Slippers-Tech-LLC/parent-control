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

Opening a report sends nothing. Send Feedback is explicit. While an error report
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
`[Dependency]` rows are omitted. There are no numbered labels, hashes, encrypted
identities, mapping files, or cross-report identity references.
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
