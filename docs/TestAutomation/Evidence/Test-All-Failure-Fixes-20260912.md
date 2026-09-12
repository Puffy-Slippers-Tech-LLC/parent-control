# Regression failure fixes — 2026-09-12

Investigated the [original aggregate report](test-all-runs/20260912T154552Z-fb5e8fa7/report.md)
and adjacent progress.json. Existing unrelated staged and unstaged work was preserved.

## Root causes and changes

- Moved the synthetic system-info fixture into `tests/support/system_info.py`;
  diagnostic export tests no longer import a collected unit-test module.
- Added the missing date to the v1.2 heading in `docs/VersionHistory.md`.
- Updated installed authorization tests to send structured `LogEvent` envelopes
  and read correlated structured `.events` records, including rotated segments.
  Cancellation, remote cancellation, no-write, and account-state assertions remain.
- The clean publishing build then exposed a real GTK icon constructor in the
  displayless feedback lifecycle unit fixture. Mocked that widget factory while
  retaining lifecycle and attachment-state assertions.
- The system run then reached a previously blocked kiosk-expiry check whose
  installed import path omitted the common diagnostics package. Added the
  installed application root alongside the broker path and restore the original
  Python search path afterward.

No product permission was relaxed; no portal files or source logs were modified.

## Verification

- Focused initial unit checks: 522 passed. Full host unit/contracts: 7,988 passed,
  111 subtests passed. Follow-up feedback fixture: 8 passed; session-expiry and
  cleanup checks: 27 passed. Isolated cleanup prerequisites: 806 passed plus
  3 subtests before protected VM operations.
- `tools/run-tests publish`: passed, including clean source/binary builds and
  Lintian. Clean build reran 7,988 unit tests and 134 private-D-Bus components.
  Evidence: `/tmp/onpc-test-publish-uironw4i` and
  `/tmp/onpc-ppa-check-52swd479`. Earlier clean-build crash retained in
  `/tmp/onpc-ppa-check-hmbj287y`.
- Full system rerun with `/tmp/onpc-test-artifacts-amq1n2k3`: all original nine
  authorization failures passed; five native enforcement checks passed. Its new
  kiosk import failure is retained at `/tmp/onpc-system-q1gx803v/evidence`.
- Selected installed kiosk-expiry rerun: all 5 executions passed, including
  installation/reboot prerequisites. Product, infrastructure, collection and
  cleanup passed: `/tmp/onpc-system-em2tsd9n/evidence`.
- Selected graphical session-expiry test passed (one test, zero failures), with
  guest evidence `/tmp/onpc-system-1qed1zld/guest-results/session.xml`. The session
  interruption left its controller at `cleanup-requested`, without a final
  aggregate report. `tools/run-tests integration check_system_recovery` verified
  recorded ownership and completed cleanup successfully; evidence:
  `/tmp/onpc-system-recovery-0ce3c4ev`. The original incomplete report remains
  incomplete; the passing guest test and recovery are separate evidence.
- Rebuilt artifacts at `/tmp/onpc-test-artifacts-cbjz875s` after harness edits.
  E2E initially refused the earlier artifact/source mismatch before VM mutation.
  With matching artifacts, `E2E-001/gdm-observation` passed, including ordered
  serial logout/GDM return, worker cleanup, and baseline restoration. All four
  outcome categories passed; controller exit 0. Evidence:
  `/tmp/onpc-e2e-evidence-qhn1n9jm`, acceptance at
  `/tmp/onpc-e2e-evidence-3p8cmlnz/acceptance.json`, raw worker artifacts at
  `/tmp/onpc-graphical-smoke-wnwei8mk`.

All originally failed and blocked checks were exercised successfully across
these runs. There was no final single `make test-all` rerun; do not replace the
original failed report or describe it as green. No test failure remains
unresolved. The VM baseline was restored and the VM left off.

The user's `tail` rule request was already satisfied by
`/home/edgar/.codex/rules/default.rules:41`; no duplicate rule was added.
Subsequent reads use quoted literal paths, including package filenames with `~`.
