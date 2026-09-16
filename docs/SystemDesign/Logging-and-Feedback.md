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

### Investigation coverage

The broker records dispatch outcomes, authorization and cancellation categories,
grant arithmetic, write/readback verification, revocation, rollback, extension
activation, execution-policy reconciliation, application termination counts,
preference persistence, startup timings, migration, and uninstall outcomes.
Parent, child, and kiosk events record displayed calculation inputs, request
and countdown transitions, session preparation, UI/resource failures, editor
lifecycle, and feedback collection/delivery/retry outcomes.

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
second-resolution expiry with the next local midnight, avoiding the fractional
second rounding mismatch reproduced at 12:48:10.349 on September 12, 2026.
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

The shared feedback dialog in Parent App, Child App, and Kiosk App sends
feedback from an unprivileged worker directly to
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
without exposing management controls. Repeated failures preserve the active
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

Drafts, selected file bytes, and frozen retries remain in memory until app exit;
closing the dialog preserves them and allows an in-flight worker to continue.
Successful sending clears the draft and, while feedback is visible, immediately
hides the feedback window and opens a modal thank-you confirmation on its owning
window. The confirmation stays open until the user dismisses it with **Close**
or another manual dismissal action; there is no countdown. When the submitted
report includes a reply email, it adds a note that support may contact the user
with follow-up questions. Error-report close callbacks run only after the
confirmation is dismissed. Background
completion does not reopen feedback that the user already closed.
The administrator can explicitly save a diagnostic ZIP to a chosen location.
The broker's [collector](../../broker/oh_no_parent_control/diagnostics.py)
reads only regular structured event files from each component's three newest
available local dates (not necessarily consecutive calendar days), rejects symlinks and hard
links, and limits input to 16 MiB, records to 12,000, and the ZIP to 2 MiB. The export method accepts no
path, UID, date, or component selector. Collection runs off the dispatch thread,
with one outstanding export through reply delivery. Collection errors expose
only a generic error; diagnostic records contain categories and byte counts.
The shared [client](../../common/oh_no_parent_control_ui/diagnostics.py) uses
this method for both feedback and downloads, including from child accounts.
The transport separately caps an attached log ZIP at 2 MiB,
user attachments at five files of at most 5 MiB each, and all attachments plus
logs at 8 MiB. Collection or size failures allow sending without diagnostics.

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

The matching portal handler must be deployed before releasing this client:
older handlers reject the generic multipart fields. A frozen submission retains
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
