# Diagnostic download layout — 2026-09-12

## Findings

The one-time test-machine download contained four files: `events.jsonl`,
`report.txt`, `manifest.json`, and `system-info.json`. It contained 63 events
(48 broker, 15 parent) spanning approximately 90 seconds in one broker
diagnostic segment. Collection reported no invalid records, truncation,
missing component directories, or write failures. This is not evidence that
older source logs were deleted or that child/kiosk operations never occurred.

The structured export implementation intentionally stopped reading older
`.log` files, combined component events, and discarded their source dates.
Its three-date selection was global across components. Local structured
storage still retains three dates per component. The downloaded snapshot
cannot establish whether older text logs remain on the test machine.

The 67,313-byte system file included 777 recursively collected dependency
rows; 672 were anonymous `[Dependency]` rows. Those rows could not identify
which integration needed attention.

The downloaded files remain untouched in the ignored `/diagnostic-logs/`
directory. No downloaded contents were added to source control or fixtures.

## Correction

- New downloads and feedback attachments contain the four component folders,
  readable `<component>/YYYY-MM-DD.log` files, and one `system-info.json`.
- Each component independently contributes its three newest available source
  dates. Source rotations and incident duplicates are merged; original normal
  file dates take precedence over later incident copies. Incident-only context
  can include earlier observations, explicitly explained in the log header.
- System information retains OS/kernel, application version, architecture,
  timezone/session type, account counts, 20 named runtime packages and bundled
  Quill. It also contains health, collection counters, and log record counts.
  There is no dependency-closure traversal or anonymous package inventory.
- Catalogue validation, filesystem link rejection, record/input/ZIP bounds,
  incident priority, and transport rebuilding remain enforced. Readable text
  is parsed and reconstructed from closed fields, not accepted as free text.
- Previous structured broker snapshots are converted to `undated.log` because
  their dates cannot be recovered. Newly collected broker exports preserve
  source dates. Original free-form text logs are never imported.

See the [logging and feedback contract](../../SystemDesign/Logging-and-Feedback.md).

## Validation

The focused diagnostic/report/system-info/feedback tests passed: **491 tests**
across `test_diagnostic_report.py`, `test_diagnostics.py`, `test_logs.py`,
`test_diagnostic_export.py`, `test_diagnostic_privacy.py`, `test_system_info.py`,
`test_feedback_transport.py`, and `test_feedback_collection.py`, using
`tools/run-unit-tests` with explicit selections and `-q`. After strengthening
the system-field ZIP tampering test, its 38 tests passed again.

`tools/run-unit-tests 'tests/unit/test_package_configuration.py' -q` passed
34 tests. `tools/run-tests source`, `git diff --check`, and the design-document
link check passed. `make build` succeeded from the shared working tree and
included the new report module in the package. This does not qualify an
installed test-machine download or remote feedback delivery. No deployment,
portal change, or support message was performed.

## Activation and compatibility

Broker export changes activate at `process-restart`; frontend/shared request
code loads on new processes, with child/kiosk session payload activation at
`session-renewal`. Ship and restart matching broker/frontends together: older
frontend validators reject schema 3. The new frontend accepts earlier
structured broker snapshots with the explicit undated fallback. The D-Bus
signature, generic portal attachment contract, and saved application data are
unchanged; no saved-data migration is required.
