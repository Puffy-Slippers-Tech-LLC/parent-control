# Privacy notice update for release

Status: draft for the publisher to apply to the
[product privacy page](https://tech.puffyslippers.com/oh-no-parent-control/privacy/)
before releasing the feedback-enabled application. The page retrieved on
2026-09-06 still states that the app transmits no information to the publisher.
That statement does not describe the optional feedback feature. The publisher
provided this page as the retention reference; a fresh retrieval on 2026-09-06
still contained no feedback-retention section. The publisher has since supplied
the disclosure below; the portal session is applying it to the website and
operations guide.

Keep the existing local-account, screen-time, app-policy, password handling,
access-control, and local log-retention explanations. Replace the absolute
no-transmission statements in the introduction, “What we do not collect,” and
“Network access and other services” with the following text, and add the
feedback section. Set the effective date when the update is published.

## Introduction replacement

Oh No! Parent Control manages family screen-time and application rules locally
on your computer and does not require an online account. Parent-control features
work without an internet connection. If an administrator chooses to send
feedback, the app sends the information selected for that report to Puffy
Slippers Tech LLC over an encrypted HTTPS connection.

## Optional feedback and troubleshooting reports

The Parent App lets an administrator send a feedback message. A report includes
the message, its formatting when applicable, and the app version. You may also
provide a reply email address and choose files to attach. Recent diagnostic
logs are included by default when available; you can remove them before sending.
Attached files include their filenames and
contents; the app does not send their original folder paths. Files or messages
you select may contain personal information, so review them before sending and
do not include passwords or information you do not want to share.

An attached diagnostic archive contains eligible product logs from the three
newest log dates, even when there are gaps between those dates. Routine product logs are designed to omit
account names, credentials, application paths, and feedback contents. You can
send feedback without attaching logs or files. You can also save a diagnostic
archive locally; saving it does not send it to us.

Draft messages and selected attachments stay in the application's memory.
Closing the feedback window preserves the draft while the app remains open,
and a report already being sent may continue. A failed submission may be
retried automatically for up to 15 minutes. Exiting the application discards
the in-memory draft and retry state; there is no saved submission queue.
Information already received by the feedback service is handled by that service.

## Collection wording replacement

The app has no analytics, advertising, tracking pixels, cloud sync, or remote
parent dashboard. It does not automatically send local account information,
parent-control preferences, or detailed usage records to Puffy Slippers Tech.
Information you explicitly include in a feedback report is the exception to
local-only processing. The app does not record your screen, keystrokes,
messages, browsing history, camera, microphone, or location. It does not receive
the administrator password entered into Ubuntu's authentication prompt.

## Network wording replacement

Parent-control features operate locally. Sending optional feedback connects to
Puffy Slippers Tech's feedback service. Ubuntu or the package manager may
connect to services configured by the computer owner to download updates.
Opening a website or email link launches the computer's browser or email
program; those services have their own privacy practices.

## Publisher verification before publication

The client now uses this disclosure, matching the portal and operations guide:

> Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support. Retention depends on our support mailbox and service providers, including their backup policies. We do not currently guarantee deletion within a fixed period.

Verify the deployed endpoint, forwarded email, attachments, diagnostic archives,
backups, and service-provider copies before publishing any fixed deletion deadline. Record the actual
purpose, recipients/processors, retention, and contact/deletion route in the
published notice. Those server practices cannot be established from this app
repository or by sending a test report. No feedback was sent during this review.

Client behavior was reviewed against `feedback.py`, `feedback_transport.py`,
`diagnostics.py`, and `SystemDesign/Logging-and-Feedback.md`. This draft describes
the application; it does not assert unverified server practices.
