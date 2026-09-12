# Feedback system information and asynchronous collection

User-directed implementation following the investigation-only review. Existing
staged diagnostics/privacy work was preserved. This change extends the shared
client; no portal files, remote delivery configuration, installed app, or VM
baseline were changed.

## Result and privacy boundary

The [owning contract](../../SystemDesign/Logging-and-Feedback.md#system-information-and-collection-state)
describes the source projection, account-count scope, dependency traversal,
schema compatibility, and dialog states. Opening feedback asynchronously
prepares a validated schema-2 ZIP containing `system-info.json`. Send remains
disabled until ready; editing and Close remain available. Download and Send
use the same bytes. Failure offers retry or explicit diagnostic removal.

System information contains OS/app/kernel versions, architecture, effective
frontend timezone/offset, session type, runtime dependency versions, and local
interactive administrator/non-administrator counts. It retains no names, UID
lists, hostname/device IDs, addresses, raw environment dumps, account mappings,
package origins, arbitrary output, or exception text. Version projection drops
all packaging/custom suffixes and epochs; unapproved dependency names use the
same `[Dependency]` label. There are no identity hashes or numbered aliases.
This deliberately limits package-revision diagnosis and package identification
outside the shipped name allowlist. Unknown/partial results are explicit.

The frontend accepts schema-1 broker output and builds schema 2 locally. No new
D-Bus method or saved-data migration is needed. New frontend launches load the
change; shared child/kiosk activation remains `session-renewal`. Packaging adds
the collector, shared privacy helper, fixed timezone-name catalogue, and the
standard `python3-apt` runtime/build dependency. Existing setup dependency
orchestration covers it without a new entry point.

## Verification

- Focused unit selection: **475 passed**. Command:
  `tools/run-unit-tests tests/unit/test_system_info.py tests/unit/test_feedback_collection.py tests/unit/test_diagnostic_export.py tests/unit/test_diagnostic_privacy.py tests/unit/test_diagnostics.py tests/unit/test_feedback_transport.py tests/unit/test_error_reporting.py tests/unit/test_logs.py -q`.
  Covers schema-1/2 compatibility, hostile field/ZIP mutation, irreversible
  projection, private exception suppression, cyclic/transitive/virtual/missing
  dependency cases, count scope/completeness, timezone overrides, send/download
  snapshot reuse, pending/failure/retry/reopen/destruction states, and existing
  transport/error/log regressions.
- UI selection: **15 passed** in 114.46 seconds. Command:
  `tools/run-ui-tests --timeout 360s tests/ui/test_parent_feedback.py tests/ui/test_error_feedback.py -q`.
  The launcher first passed **806 cleanup-safety tests and 3 subtests** in
  isolation. UI checks exercise the production shared dialog in Parent,
  Child-overlay and Kiosk, including delayed collection, editor responsiveness,
  Send sensitivity, privacy disclosure, failure recovery, draft preservation,
  restrictions and submission outcomes. Preview transports send no real email.
- Direct `make build` stopped during Debian's clean step because the existing
  `tools/__pycache__/test_launcher.cpython-314.pyc` and its directory were
  root-owned. No ownership changes or privileged cache deletion were attempted.
- `tools/run-tests artifacts build`: **build and verification passed** using the
  maintained isolated-source builder. Artifacts are under
  `/tmp/onpc-test-artifacts-_trlz5m9`; package:
  `package/oh-no-parent-control_1.1+ppa1~ubuntu26.04.1_amd64.deb`.
  The isolated source includes current untracked production additions as well
  as tracked changes, and excludes the unrelated Python cache.
- `git diff --check` and local Markdown link validation passed.

These results establish local source, collector/validator behavior, shared UI
behavior, and package buildability. They do not qualify installed VM collection
or external delivery, and no feedback was sent to the real endpoint. The direct
checkout build's root-owned-cache obstacle remains an environment issue.
