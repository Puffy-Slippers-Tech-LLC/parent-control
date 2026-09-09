# Kiosk error and feedback investigation — 2026-09-09

The installed app is the staged baseline. Another session is changing feedback
delivery in the working tree; its transport changes and fixtures are preserved.
No installed app, service, log, portal checkout, or deployment was changed by
this investigation.

## Error shown at approximately 15:38 Pacific

The kiosk log records `time estimate unavailable` at 15:38:29, 15:39:59, and
15:44:29. At each timestamp the broker records `GetTimeStatus` failing with
`TimerUsageError`, translated to `BackendFailure`. The system journal records
`malcontent-timerd` exiting at its inactivity timeout at those exact three
timestamps. The next queries succeed after D-Bus reactivates the timer daemon.
The kiosk remains alive and completes an approved request at 15:45:01.

This evidence strongly identifies a timer-service idle-shutdown race in the
periodic usage query, rather than process termination. The installed helper
turns every GLib failure into exit 69 and discards the underlying error text,
so the precise original D-Bus error code cannot be recovered from these logs.
The supported [GIO D-Bus errors](https://docs.gtk.org/gio/error.DBusError.html)
distinguish owner loss and missing replies from permission or argument errors.

The [usage helper](../broker/oh-no-parent-control-query-usage) now retries only
`NoReply`, `NameHasNoOwner`, and `ServiceUnknown`, at most three total attempts
within a shared 25-second budget. Each attempt retains the same reader identity
and target. The broker still fails closed on exhausted reads. Adapter failures
now log a bounded category and numeric return code without exception text.

## Diagnostic attachment

At 15:38:51 and 15:44:34, the kiosk reports log collection failing with
`PermissionError`. The former collector runs as the frontend account, but
product logs are protected by `root:sudo` directory/file permissions. The kiosk
account cannot read that directory.

The user explicitly requested all product logs in every app. The new
`ExportDiagnosticLogs() -> (ay archive)` broker method authorizes local
administrators, the configured kiosk, and eligible children, and exports the
same archive for all three frontends. It accepts no path, UID, date, or component
selector. It rechecks roles before delivering, limits outstanding exports to
one, rejects symbolic/hard links and nonregular log files, and retains the
16 MiB input/archive limits and latest three available log dates. The shared
frontend calls it for both attachment preparation and downloads. File permissions
remain protected. No upload occurs until the user sends feedback.

Broker code and the additive D-Bus contract require `process-restart`; frontend
processes must load the updated shared client. No saved-data migration or portal
API change is involved. See [logging and feedback](SystemDesign/Logging-and-Feedback.md).

## Reported clearing after removal

The staged and current `FeedbackDialog._toggle_attachment` implementations
only toggle the log attachment. They neither submit nor clear the editor.
`_submission_done` clears the draft after confirmed successful submission,
including submission via **Send without logs**. The kiosk logs show a successful
submission without logs at 15:44:38. They do not record attachment-button clicks,
so they cannot establish which control preceded the reported text loss.

A new graphical regression covers both kiosk and child overlay: preserve the
prefilled report and an added user note through collection failure and removal,
send nothing on removal, and include the same draft in a subsequent explicit
submission. It uses the real shared dialog and editor with a local fake transport.
This issue remains unverified pending graphical execution and clarification of
the clicked control; no speculative editor change has been made.

## Validation

The first `make check-unit` run reported 5811 passed and 10 failures. Failures
included executable launchers on the `noexec` shared checkout and concurrent
test work outside this change. The follow-up run includes the new export and
usage-retry tests: **5840 passed, 9 failed** in 178.88 seconds. All 14 new
diagnostic-export tests, eight usage-retry tests, six collector/download tests,
and seven service-contract tests passed. The nine remaining failures exercise
launchers on the `noexec` checkout (slice inspection, document checks, E2E Make
dispatch, guest guard, and guest preparation). `git diff --check` passed.

The checkout is a virtiofs mount with `noexec`. Direct execution of the approved
read-only, unit, and diagnostic launchers returns permission denied even outside
the sandbox. The installed diagnostic helper successfully read the journal.
`make check-unit` uses its existing supported recipe and can run. Graphical
tests require an executable checkout or the explicitly requested one-time
exception to invoke the unchanged, validated UI launcher through its interpreter.
