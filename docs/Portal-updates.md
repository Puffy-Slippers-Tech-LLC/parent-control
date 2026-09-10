# Portal updates for Oh No! Parent Control

Update the public privacy page and related help text with the content below.
Client/server feedback delivery has already been validated; this task is limited
to content updates.

## 1. Update privacy and help content

Update https://tech.puffyslippers.com/oh-no-parent-control/privacy/ and related
help text. Replace Parent-App-only descriptions and incomplete statements about
diagnostic access with these facts:

- **Feedback is available in Parent App, Child App, and Kiosk App.** All three
  support optional feedback and editable error reports. Opening a report sends
  nothing. The user must select **Send Feedback**.
- **Submissions may include** the message, formatted content, reply email,
  app version, selected attachments, and an optional diagnostic ZIP. Local file
  paths, saved parental-control preferences, and provider secrets are not sent.
- **Diagnostic archives can include all four components:** broker, parent,
  child, and kiosk. Local administrators, eligible children, and the configured
  kiosk account can obtain the archive through the app. Direct access to log
  files remains restricted. This does not grant access to saved preferences.
- **The dedicated kiosk has limited file controls.** It can attach the
  app-provided diagnostic ZIP, but cannot add arbitrary files, save diagnostic
  ZIPs, or launch the external privacy page. It shows the privacy disclosure
  in-app. These restrictions do not apply to the Child App request overlay.
- **Drafts stay in app memory until app exit.** Closing ordinary feedback
  preserves the draft and may leave sending/retries running. Successful sending
  clears the draft. There is no persistent submission queue.
- **Stopping an error report cancels pending retries.** While sending, its
  **Stop sending and close** action stops further retries. A submission already
  accepted by the service cannot be recalled.

Use this retention disclosure on the privacy page and in relevant support or
operations documentation:

> Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support. Retention depends on our support mailbox and service providers, including their backup policies. We do not currently guarantee deletion within a fixed period.

Do not promise a fixed deletion period without implementing and verifying it.

## 2. Verify completion

1. Check the privacy page and related help text cover all three apps, diagnostic
   access, dedicated-kiosk restrictions, draft lifetime, cancellation, and the
   retention disclosure above.
2. Remove contradictory Parent-App-only descriptions and claims that standard
   users cannot obtain diagnostic logs through the app.
3. After publication, check the rendered pages and report the updated URLs and
   any content still awaiting publication.
