# Logging, diagnostics, and feedback

[System design overview](../System-Design.md)

Read this for component logs, privacy at logging call sites, diagnostic
archives, the feedback editor, and HTTP submission/retry behavior.

Implementation: [logs.py](../../broker/oh_no_parent_control/logs.py), [broker service unit](../../data/systemd/oh-no-parent-control-broker.service), [feedback.py](../../common/oh_no_parent_control_ui/feedback.py), [feedback_transport.py](../../common/oh_no_parent_control_ui/feedback_transport.py), [rich_text_editor.py](../../common/oh_no_parent_control_ui/rich_text_editor.py), [diagnostics.py](../../common/oh_no_parent_control_ui/diagnostics.py).

## Logging

The broker is the sole file-log writer. Logs are under
`/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log`, owned by
`root:sudo` so Ubuntu administrators can read them and other users cannot.
Parent, child, and kiosk records are forwarded over D-Bus after role checks;
broker records are written internally. A component's first event on a new day
prunes that component beyond the newest ten dated files.

The service unit runs the broker as `root:sudo`; directories use mode `0750`
and dated files use mode `0640`. The writer validates component, level, and
message length and escapes line breaks. It does not automatically redact
arbitrary message text: call sites must omit PII, credentials, application
paths, and feedback content. Use operation names, counts, error categories,
and placeholders such as `[Child user]`.

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

[errors.py](../../common/oh_no_parent_control_ui/errors.py) captures a public
title and explanation followed by a separator and the internal exception
messages (including causes). Reports use an editable, bounded plain-text draft;
exception text is never inserted as executable HTML or written to logs. Logs
record component and exception type only. The subject is
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
the same Child App reporter over a private subprocess stdin pipe. Error content
never appears in command arguments. Only its retained subprocess may be stopped
when the extension is disabled.

Opening a report sends nothing. Send Feedback is explicit. While an error report
is sending, its Close action becomes **Stop sending and close**, which cancels
pending retries before leaving. A request already accepted remotely cannot be
recalled. Ordinary feedback retains its existing background retry behavior.
All three apps request the same full product-log archive from the broker's
`ExportDiagnosticLogs` method. The broker validates the caller as a local
administrator, configured kiosk, or eligible child before collecting and again
before replying. This deliberately permits those roles to review all four
components' diagnostic logs; raw log-directory permissions remain unchanged.
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
reads only regular dated product logs from the three newest available local log
dates (not necessarily consecutive calendar days), rejects symlinks and hard
links, and limits input and ZIP size to 16 MiB. The export method accepts no
path, UID, date, or component selector. Collection runs off the dispatch thread,
with one outstanding export through reply delivery. Collection errors expose
only a generic error; diagnostic records contain categories and byte counts.
The shared [client](../../common/oh_no_parent_control_ui/diagnostics.py) uses
this method for both feedback and downloads, including from child accounts.
The transport separately caps an attached log ZIP at 2 MiB,
user attachments at five files of at most 5 MiB each, and all attachments plus
logs at 8 MiB. Collection or size failures allow sending without logs.

The additive D-Bus contract and broker collector activate with `process-restart`.
New app processes load the updated export client; kiosk/shared request payloads
retain `session-renewal`. Ship the broker and frontend together. An older broker
reports export unavailable and the frontend preserves the draft for sending
without logs. There is no portal contract or saved-data migration for this change.

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
