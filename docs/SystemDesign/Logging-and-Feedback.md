# Logging, diagnostics, and feedback

[System design overview](../System-Design.md)

Read this for component logs, privacy at logging call sites, diagnostic
archives, the feedback editor, and HTTP submission/retry behavior.

Implementation: [logs.py](../../broker/oh_no_parent_control/logs.py), [broker service unit](../../data/systemd/oh-no-parent-control-broker.service), [feedback.py](../../parent/oh_no_parent_control_parent/feedback.py), [feedback_transport.py](../../parent/oh_no_parent_control_parent/feedback_transport.py), [rich_text_editor.py](../../parent/oh_no_parent_control_parent/rich_text_editor.py), [diagnostics.py](../../parent/oh_no_parent_control_parent/diagnostics.py).

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

The Parent App sends feedback from an unprivileged worker directly to
`https://tech.puffyslippers.com/api/oh-no-parent-control/feedback`. It sends
plain text, optional semantic HTML, optional reply email, app version,
user-selected attachment basenames and bytes, and an optional diagnostic ZIP.
The transport disables ambient credentials/proxy settings and redirects; it
does not send local attachment paths, private preferences, or provider secrets.
Use this disclosure consistently in the Parent App, website, and portal
operations guide:

> Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support. Retention depends on our support mailbox and service providers, including their backup policies. We do not currently guarantee deletion within a fixed period.

The Parent App footer summarizes this as “Feedback is emailed to support.”
Its Privacy link opens the full disclosure and diagnostic-log explanation.

Server-side sanitization, email
routing, and retention enforcement belong to the separately deployed endpoint.

The editor is locally bundled Quill 2.0.3 inside an ephemeral WebKitGTK 6 web
view. The in-memory page's content-security policy denies network sources and
navigation away from the editor is blocked. Editor content crosses the local
message bridge as plain text, semantic HTML, and a Quill delta used to restore
the draft after a web-process restart.

Drafts, selected file bytes, and frozen retries remain in memory until app exit;
closing the dialog preserves them and allows an in-flight worker to continue.
The administrator can explicitly save a diagnostic ZIP to a chosen location.
Diagnostic export reads only regular dated product logs from today and the
previous two local calendar days, rejects symlinks, and limits input and ZIP
size to 16 MiB. The transport separately caps an attached log ZIP at 2 MiB,
user attachments at five files of at most 5 MiB each, and all attachments plus
logs at 8 MiB. Collection or size failures allow sending without logs.

## Multipart and retry contract

The client sends multipart fields `message`, optional `messageHtml`,
`replyEmail`, and `appVersion`, repeated `attachments` file parts, and an
optional `logs` ZIP part. A frozen submission retains one `Idempotency-Key`
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
