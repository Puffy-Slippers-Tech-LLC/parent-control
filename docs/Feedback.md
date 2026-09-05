# Parent feedback design and delivery investigation

Status: dialog design implemented; log collection, compression, and submission
are deliberately deferred. The dialog has an editable message, optional reply
email, and a removable/restorable log attachment option. It explicitly labels
the current preview and disables Send Feedback. No draft is persisted and no
feedback text or email address is logged.

The menu uses heavier circular dots and the same lavender background and purple
foreground as the selected daily allowance. Keyboard focus and pointer hover
use the same menu highlight. The dialog follows the parent app's light surface,
rounded cards, spacing, and purple accent.

## Recommendation

Use a small HTTPS feedback endpoint operated by the product owner, with email
delivery performed on the server. This is a design recommendation, not an
implemented integration. It supports a single in-app flow with a private log
attachment and an optional reply address, without depending on a configured
desktop mail client or a user's GitHub account. It does introduce hosting,
abuse prevention, and delivery monitoring responsibilities.

| Option | Fit and tradeoff |
| --- | --- |
| Own service → email | Best fit for the proposed dialog: accept message and ZIP together, return a receipt, and send the support email on the server. Requires an operated service, request limits, and bounded private retention. Keep all mail-provider credentials on the server. |
| Default email app | Reasonable lower-maintenance alternative. The supported XDG Email portal accepts subject, body, and attachment file descriptors, but relies on a compatible default mail client. Opening a composer is not confirmation that the feedback was sent. |
| GitHub issue | Useful for public bug tracking after triage. Public repository uploads are accessible without authentication; this is a poor default destination for diagnostic logs. The browser attachment flow requires choosing or dragging a file, and a prefilled issue URL does not automatically attach a local ZIP. |

The [XDG Email portal documentation](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Email.html)
defines attachment support and its mail-client compatibility requirements.
A plain [mailto URI](https://www.rfc-editor.org/info/rfc6068/) does not define a
portable attachment mechanism. If choosing desktop email, use the portal and
verify the target distribution's installed backend and supported clients; offer
an explicit failure state when composition cannot be launched.

[GitHub's attachment documentation](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files)
supports ZIP files and documents public upload visibility and the browser upload
flow. [Prefilled issue links](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue)
can supply issue text. Promote actionable feedback to GitHub after review, with
the reporter's personal information and original logs excluded.

## Proposed attachment and send behavior

1. Prepare one bounded ZIP of the past three days of product component logs locally in a private
   temporary directory, using an explicit allowlist of dated regular files under
   `/var/log/oh-no-parent-control/`. Include today and the previous two local
   calendar dates across broker, child, parent, and kiosk logs. Missing dates
   do not cause older files to be included. Keep the existing ten-file retention
   per component; the three-day limit applies only to the feedback attachment.
   Do not collect journals, home files, or saved
   child preferences. Reject symlinks and cap both input size and archive size.
   The administrator can already read these root:sudo logs; do not add a
   privileged collection service unless deployment testing proves one necessary.
2. Show preparation progress, then the actual archive name and compressed size.
   Allow reviewing the included files and removing the attachment before sending.
   Removal excludes the archive from the request. Feedback must still work when
   logs are unavailable, too large, or excluded. Never upload during preparation.
3. Retain the product's PII-free logging contract and review/redact the exported
   content as well. Never put the user's feedback text, reply email, archive
   contents, or personal file paths into application logs.
4. Send only on explicit submission. The HTTPS service should enforce message
   and attachment limits, rate limits, and safe fixed email headers. Treat the
   attachment as opaque data; do not extract it server-side. A desktop app cannot
   safely keep a shared service secret. An optional reply address is data, not an
   authorization credential.
5. Acknowledge receipt only after durable acceptance. Use an idempotency token to
   prevent duplicate reports on retries; retain the draft after failure. Distinguish
   service acceptance from delivery to the support mailbox. Delete temporary
   archives when discarded or completed, and specify a bounded server retention
   period before launch.

No saved-data schema, setup, broker contract, or system integration changes are
part of the current UI work. Activation is `none`: the parent UI is loaded when
the app is reopened, with no broker restart, session renewal, or reboot needed.
