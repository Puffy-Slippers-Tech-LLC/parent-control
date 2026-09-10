# First release: deployed feedback disclosure and contract

Release preparation on 2026-09-10 targets product `1.0`, candidate package
`1.0+ppa1~ubuntu26.04.1`, based on client commit
`9cb8059a4a02f8568021de10609ee5d98e629fc5`. This client session has not changed
the portal checkout or deployed anything. A separate portal session must
implement and verify the website correction before client publication.

## Reason and observed deployed behavior

The [public privacy page](https://tech.puffyslippers.com/oh-no-parent-control/privacy/)
was retrieved successfully on 2026-09-10. Its feedback retention disclosure
matches the client: submissions are emailed to support; mailbox/service-provider
and backup retention applies, with no guaranteed fixed deletion period.

However, the introduction, optional-feedback section, draft lifetime, and policy
scope describe feedback only from Parent App. The local-information section
says other standard users cannot read product logs. That is incomplete for this
release: eligible children and the configured kiosk account can explicitly
obtain the same diagnostic archive through the broker, while direct log-file
access remains protected. All three apps support optional feedback/error reports.
The page also says users can save logs for review without explaining the kiosk
restriction on file saving. These differences prevent calling the deployed
notice consistent with the release.

## Requested website contract

Align the privacy page and relevant help text with the client's
[logging and feedback design](SystemDesign/Logging-and-Feedback.md):

- Cover Parent App, Child App, and Kiosk App feedback and editable error reports.
  Opening a report sends nothing; explicit Send Feedback submits it.
- Explain that the authorized roles can receive diagnostic logs from all four
  product components through the app. Distinguish this from direct filesystem
  permissions and access to saved parent-control preferences.
- Explain that the dedicated kiosk does not offer arbitrary file attachments,
  saving diagnostic ZIPs, or an external privacy-page launch. It shows an
  in-app disclosure and can attach the broker-provided diagnostic ZIP.
- Describe draft/retry lifetime in the relevant app process, and error-report
  cancellation accurately. Do not promise recall of an accepted submission.
- Preserve the existing retention disclosure. Verify the deployed support
  recipient and provider practices before changing server-side promises.

## Generic delivery API: verify deployed compatibility

The client composes branding, titles, component labels, version metadata,
formatted email content, and diagnostic attachments. The portal must remain a
generic delivery service; no component-specific report formatting is requested.
Its deployed handler version has not been established by this read-only review.
Older product-specific multipart handlers reject this client's generic fields.

The current client sends HTTPS POST to
`/api/oh-no-parent-control/feedback`, with multipart fields and a stable
`Idempotency-Key` per explicit submission. Illustrative wire content:

```text
Idempotency-Key: <one submission identifier>
Content-Type: multipart/form-data; boundary=<generated boundary>

title = [Oh No! Parent Control] Child App Error Report
body = <client-composed plain text, including version and report content>
bodyHtml = <optional client-composed semantic HTML>
replyTo = <optional user-provided reply email>
attachments = <optional selected file bytes and basename; repeated field>
attachments = <optional diagnostic ZIP named oh-no-parent-control-logs.zip>
```

The required successful response is:

```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{"ok": true, "receiptId": "<optional receipt identifier>"}
```

Preserve validation, HTML/basename sanitization, deduplication, and upload limits.
The client uses a 30-second request timeout and a bounded 15-minute retry window.
It retries transient network/server failures, 408, and unconfirmed 202 responses;
429 uses a bounded Retry-After delay. 409 expires the submission and 413 reports
size failure. Never infer successful delivery merely from an HTTP endpoint
being reachable.

## Acceptance and release dependency

1. Deploy and retrieve the corrected public privacy/help pages; verify all
   three frontends, diagnostic access, kiosk restrictions, and retention agree
   with the client design and UI.
2. Inspect the deployed handler's generic multipart contract and configured
   recipient without exposing credentials or private addresses in evidence.
   Record deployment identity and recipient verification as a bounded result.
3. Run the portal's existing contract tests for generic fields, repeated
   attachments, HTML sanitation, limits, idempotency, and success/error responses.
   Any real email test needs explicit delivery authorization and a dedicated
   recipient; this handoff does not authorize sending mail.
4. Return deployment/test evidence to the client release session. The website
   correction and compatible handler must precede release publication. No
   client saved-data migration or API redesign is requested.

The [publishing guide](Publishing.md) owns the remaining package checks and
publication decision. Local release evidence is retained beside the candidate
in `/tmp/onpc-release-20260910-first/`.
