# 010 — Diagnostics survive failed and recovered components

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and route

Required tasks: 002, 004, 007, 009.
Read the [master](../Reliability-Plan.md),
[diagnostic contract](../SystemDesign/Logging-and-Feedback.md), child error and
process-exit handlers, dependency collectors, catalogue validators and existing
`check_e2e_diagnostic_export.py`/host export tests. Reuse the canonical report
collection/export owner; no feedback submission or external message is involved.

Planned qualification (unimplemented): `check_e2e_failure_diagnostic_recovery`.
Reuse task 002/007's fault mechanics without duplicating their acceptance matrix.

## Finite histories and expected results

1. Produce one reviewed timer failure while the child reporter is already open;
   recover timer reads, then use the existing report owner to perform a fresh
   normal collection and export. Preserve the original operation/stage/category
   and repeated-failure evidence despite later success and the reporter's
   duplicate-window suppression. A snapshot collected before the failure need
   not acquire later events; do not change frozen snapshot or submission bytes.
2. Exercise the recorded app crash from task 007 with no surviving kiosk app;
   collect through the broker and export after reentry. Retain abnormal
   exit/signal and available renderer/security markers, with bounded source
   completeness accurately reported rather than inferred.
3. Use isolated host/component fault coverage for diagnostic writer/transport
   failure during successful refresh, lock and cleanup. These operations must
   retain their result; diagnostic failure must not create a recovery loop.

Inspect the validated archive through maintained readers, with private canaries
for exception messages, usernames, paths, remote names and arguments. Keep only
approved fixed fields and provenance. A placeholder reporter exception is not
the original failure, communication completion is not process success, and a
healthy later event cannot erase the failing stage's incident.

## Validation and close-out

Run affected catalogue, Gio, export, process-lifetime and privacy tests first.
Require both installed histories and an actual valid downloaded export on each
target, plus the isolated diagnostic-failure selection. Preserve bounded
collection/unavailable results, candidate identities and all owned cleanup.
Fix missing causal evidence or failure-isolation defects at their existing
producer/collector boundary; do not attach raw journals or change transport.
Build as required and update existing diagnostic/coverage owners.
