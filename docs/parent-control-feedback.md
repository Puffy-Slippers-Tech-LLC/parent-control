# Parent Control feedback API

The portal implements `POST https://tech.puffyslippers.com/api/oh-no-parent-control/feedback`
as a Cloudflare Pages Function. It uses the existing Brevo sender and inbox:
`BREVO_API_KEY`, `CONTACT_FROM_EMAIL`, and `CONTACT_TO_EMAIL`. No app secret,
database, object storage, or new paid service is required. Deployment and the
operations steps below are needed before activating Send Feedback in the app.

The parent app integrates this endpoint in its Send Feedback dialog. Production
sending is enabled in `parent/oh_no_parent_control_parent/feedback_transport.py`
following confirmation that the backend is deployed. The canonical route is
`/api/oh-no-parent-control/feedback` (not `/api/parent-control/feedback`).

The configured feedback and attachment retention period is **7 days** in Brevo
and the support mailbox. The dialog discloses that feedback and optional
attachments are sent to support and retained for that period.

The desktop sends using Requests with library-generated multipart boundaries,
a 30-second timeout, TLS verification, and no redirects or client credentials.
It freezes each report and every attachment for automatic retries with the same key, using
5/15/60-second backoff plus jitter and honoring rate-limit delays within the
15-minute token window. HTTP 409 stops retries and presents an explicit
“Submit again (may duplicate)” action. HTTP 413 preserves the report so files or
logs can be removed. Unavailable local logs offer “Send without logs”; this
explicit action creates a new submission.

Drafts, user-file bytes, and optional downloaded ZIP bytes are held in memory. Closing and
reopening the dialog preserves them for the parent-app session; retries continue
while the app is open. Quitting the app discards the draft and stops retries.
Only HTTP 202 with JSON `ok: true` clears the draft and displays
“Feedback submitted.” The receipt is retained in memory. Logs contain attempt
counts, status codes, and failure categories, never report contents, email
addresses, filenames, attachment bytes, response bodies, or submission tokens.

`SENDING_ENABLED` is the release switch for sending; it can be disabled without
changing the URL. `RETENTION_DISCLOSURE` must match the configured policy. The
launch checklist below still documents the required server-side operations;
client tests mock delivery and do not verify WAF or provider settings.

This parent-only change activates on the next Parent App launch (`none` under
`Package-Update.md`); it adds no system service or saved-data migration.
`python3-requests` and GTK 4's `gir1.2-webkit-6.0` binding are declared in
package dependencies and `setup.sh`. Quill 2.0.3 and its license notices are
pinned and bundled locally, so the editor loads no CDN code or other network
resource. Its ephemeral web view disables local storage, file-URL access, popup
windows, and navigation away from the in-memory editor.

## Request

Use HTTPS and `multipart/form-data`; let the HTTP library generate the boundary.
The request must include an `Idempotency-Key` header (see Retries).

| Part          | Required | Limit / meaning                                                                                      |
| ------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `message`     | yes      | Nonblank plain-text fallback, at most 5,000 UTF-16 code units before trimming. Rejects NUL.          |
| `messageHtml` | no       | Semantic rich HTML, at most 50,000 UTF-16 code units. The service sanitizes it before email.         |
| `replyEmail`  | no       | Bare reply email, at most 254 characters; blank means no reply requested.                            |
| `appVersion`  | no       | Single line, at most 64 characters.                                                                  |
| `attachments` | no       | Repeated file part: at most 5 files and 5,242,880 bytes (5 MiB) per file.                            |
| `logs`        | no       | One ZIP file, at most 2,097,152 bytes (2 MiB). Omit the part when logs are removed or unavailable.   |

Only `attachments` may repeat; other duplicate or unknown parts and files in
text fields are rejected. User attachments plus logs are limited to 8,388,608
bytes (8 MiB). The complete multipart body is limited to 8 MiB plus 256 KiB of
encoding overhead, counted while streaming even if
Content-Length is absent or incorrect. Oversized values are rejected, never
silently truncated. ZIPs require a `.zip` filename and a ZIP signature; this is
not validation of the archive's contents. The service never extracts archives.
The client sends a validated MIME type when known, but the service does not rely
on it. Filenames are reduced to a control-free basename of at most 180 Unicode
characters in both client and service; local paths are never retained or sent.

The client supports headings, bold, italic, underline, strikethrough, numbered
and bulleted lists, block quotes, code blocks, and links. The service allows the
corresponding safe structural tags and sanitizes attributes and URLs. It strips
styles, scripts, event handlers, embedded media, and unsafe URL schemes. Email
always includes the plain-text fallback even when sanitized HTML is present.

The subject is always `[Oh No! Parent Control] App feedback`. Recipient and sender
come only from server configuration. The optional reply email becomes Reply-To;
no acknowledgment is emailed to the submitter. Diagnostic logs are renamed
`oh-no-parent-control-logs.zip`; user files keep their sanitized basename. Their
bytes are forwarded unchanged using
[Brevo's base64 attachment API](https://developers.brevo.com/reference/send-transac-email).

Example (creates a token locally; running curl sends a real support email):

```bash
feedback_key=$(python3 -c 'import time, uuid; print(f"{int(time.time())}.{uuid.uuid4()}")')
curl --fail-with-body https://tech.puffyslippers.com/api/oh-no-parent-control/feedback \
  -H "Idempotency-Key: $feedback_key" \
  --form-string 'message=The daily allowance display did not update.' \
  --form-string 'messageHtml=<p>The daily allowance display did <strong>not</strong> update.</p>' \
  --form-string 'replyEmail=parent@example.com' \
  --form-string 'appVersion=1.2.3' \
  -F 'attachments=@/path/to/screenshot.png;type=image/png' \
  -F 'logs=@/path/to/reviewed-logs.zip;type=application/zip'
```

Drop either file option when it is not wanted. Do not send local paths, device
identifiers, child preferences, or additional diagnostic metadata as form fields.

## Responses

Only HTTP **202** with `ok: true` acknowledges acceptance:

```json
{ "ok": true, "message": "accepted", "receiptId": "<the submitted Idempotency-Key>" }
```

This means Brevo accepted the email request (or previously accepted this retry).
It does not confirm delivery to the support mailbox. There is no receipt lookup
endpoint or local queue. A provider/network failure never produces a success
receipt. Feedback responses are marked `Cache-Control: no-store`.

Errors from the function have `{"ok":false,"error":"<code>"}`:

| HTTP | Codes                                                                | Client behavior                                          |
| ---- | -------------------------------------------------------------------- | -------------------------------------------------------- |
| 400  | `invalid_request`                                                    | Repair multipart encoding.                               |
| 405  | `method_not_allowed`                                                 | Use POST; OPTIONS is also supported.                     |
| 409  | `idempotency_key_expired`                                            | Stop automatic retries; see below.                       |
| 413  | `request_too_large`, `attachment_too_large`                          | Keep draft; offer to remove files or logs.               |
| 415  | `unsupported_media_type`                                             | Use multipart form data.                                 |
| 422  | `validation_failed`, `invalid_attachment`, `invalid_idempotency_key` | Keep draft and correct the request.                      |
| 429  | `rate_limited`                                                       | Honor `Retry-After` (seconds).                           |
| 502  | `provider_unavailable`, `provider_error_<status>`, `send_failed`     | Keep draft; retry with the same token.                   |
| 503  | `email_not_configured`, `service_unavailable`                        | Keep draft; retry later with the same token while valid. |

Cloudflare can return a non-JSON error (including 429). The client must handle
that, timeouts, and connection failures without discarding its draft or assuming
success. Use a client timeout of at least 30 seconds; the provider call times out
after 15 seconds. CORS allows POST/OPTIONS and the idempotency header, but CORS
is not authentication or abuse prevention for a desktop endpoint.

## Retries and duplicate prevention

On the first explicit send, generate `<unix-seconds>.<lowercase-UUIDv4>`, using
the current UTC Unix time in seconds. Freeze the token, plain text, HTML, reply
address, version, user files, and ZIP bytes together for that submission. Retry that exact report
with the same token, even after a timeout; do not rebuild its archive on retry.
Back off (for example 5, 15, then 60 seconds with jitter) and honor Retry-After.

The endpoint accepts tokens for 15 minutes from their timestamp, with 60 seconds
of allowance for a client clock ahead of the server. It derives a stable,
namespaced UUID from the token and configured recipient for the email provider.
[Brevo retains idempotency keys for 30 minutes and reports duplicates using
`duplicate_parameter`](https://developers.brevo.com/docs/heterogenous-versions-batch-emails).
The shorter endpoint window prevents a delayed retry from sending again after
the provider forgets the key, including across function restarts. Do not change
the recipient configuration during a retry window.

The token identifies one immutable report. The stateless portal cannot detect
changed content under a reused token: Brevo will suppress it as a duplicate.
An edited report needs a new token and explicit submission. After expiration,
retain the draft and show that the previous send's outcome may be unknown; do
not silently generate a replacement token or retry automatically. A user can
explicitly submit again, with notice that it may duplicate an earlier report.

## Abuse controls and launch configuration

The handler enforces a local limit of 5 attempts per client IP per minute and
30 total attempts per minute per running isolate, before reading uploads. All
POST attempts count. Counters are bounded in memory and reset after a minute;
they are not shared across isolates and reset on restarts. The Cloudflare
adapter takes the address only from `CF-Connecting-IP`. When porting, pass the
hosting platform's trusted client address, never arbitrary forwarded headers.

Before enabling the app endpoint in production:

1. In the Cloudflare zone, create an edge rate limiting rule matching
   `starts_with(http.request.uri.path, "/api/oh-no-parent-control/feedback")`:
   **5 requests per IP per 10 seconds, Block for 10 seconds**. These periods
   fit the [Free plan's rate limiting rules](https://developers.cloudflare.com/waf/rate-limiting-rules/).
   Use Block, since a native app cannot complete a browser challenge. If the
   zone's one free rule is already used, extend its path expression.
2. Protect preview deployments with Cloudflare Access and restrict/redirect the
   production `pages.dev` hostname so it cannot bypass the custom domain's WAF.
   The app must use the canonical custom domain. Configure equivalent protection
   if exposing any other hostname.
3. Confirm the existing Brevo credentials and sender verification, test a real
   formatted message, ordinary file, and ZIP, then retry the same token and
   verify only one email arrives and its HTML is sanitized.
   Do not run this smoke test with real diagnostic logs.
4. Monitor provider rejection/delivery counts and the receiving inbox. Neither
   the edge rule nor local limits are a global daily email quota; distributed
   abuse can still exhaust the shared provider allowance. No billing upgrade is
   required or provisioned by this change.

These are dashboard operations, not resources provisioned by the repository.
Local limits alone do not provide distributed abuse protection.

## Retention

The function writes no feedback, reply email, filename, attachment, or client IP to logs, a disk,
or durable storage. Request buffers are released for garbage collection when
processing finishes. IP counters are only used in memory for the active minute
and cleared on the next window's request or isolate disposal.

The support email, including user files, logs, and reply address, persists in Brevo and the
recipient mailbox. Use the configured **7-day retention policy** (within the 30-day maximum) for original feedback
and attachments in both systems before launch, including trash and any exported
copies; configure provider content retention and mailbox deletion rules, or a
documented scheduled operator cleanup where automatic rules are unavailable.
Confirm those settings and applicable backup retention with the account owners.
This code cannot enforce deletion from either external system and does not
claim that it does. Keep only redacted issue summaries beyond that period.
The desktop disclosure must explain that feedback and optional attachments are sent
to support and describe the retention policy actually configured.

## Local verification

In this desktop repository, run:

```sh
/usr/bin/python3 -m pytest tests/unit/test_feedback_transport.py tests/unit/test_diagnostics.py -q
/usr/bin/python3 -m pytest tests/unit/test_ui_cleanup_safety.py -q
tools/run-ui-tests --timeout 180s tests/ui/test_parent_feedback.py -q
```

The component preview replaces the HTTP session and log collector; no real
feedback email is sent. These tests cover validation, actual multipart encoding,
response handling, immutable backoff retries, expiration, oversized attachments,
draft preservation, and success UI.

In the portal repository, run `npm test -- tests/functions`, then the repository's typecheck, lint, and
build checks. Use `npx wrangler pages dev out` to exercise the actual route.
Without local email credentials a valid report returns 503 `email_not_configured`;
invalid input should still be rejected before any provider call. Unit tests mock
Brevo and never send email. For an authorized local delivery test, provide the
existing server variables through Wrangler's local environment without committing
them. Never put provider credentials in the desktop app.
