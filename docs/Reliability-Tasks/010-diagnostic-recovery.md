# 010 — Diagnostics survive failed and recovered components

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 30–60 minutes.

## Session boundary

Deliver actual crash-evidence export after the reporter app has died. 010a
cumulatively supplies 010c's child isolation and process-exit/cleanup diagnostic
isolation; 010b supplies the distinct already-open
child reporter/timer recovery export. Session exception: crash, reentry, fresh
collection and validated download form one causal history per installed target.

## Purpose and route

Required tasks: 002, 004, 007, 009, 010a, 010b.
Read the [master](../Reliability-Plan.md),
[diagnostic contract](../SystemDesign/Logging-and-Feedback.md), child error and
process-exit handlers, dependency collectors, catalogue validators and existing
`check_e2e_diagnostic_export.py`/host export tests. Reuse the canonical report
collection/export owner; no feedback submission or external message is involved.

Planned qualification (unimplemented): `check_e2e_failure_diagnostic_recovery`,
for the dead-kiosk-app branch. Reuse task 007's fault mechanics without
duplicating its acceptance matrix or consuming only its earlier crash report.

## Finite histories and expected results

Exercise the owned app-crash mechanism qualified in 007 with no surviving kiosk
app; collect through the broker and export after reentry in this fresh attempt.
Retain abnormal exit/signal and available renderer/security markers, with bounded
source completeness accurately reported rather than inferred. Require the
original crash cause even after the new app starts successfully. Reuse 010a's
isolated failure regressions and 010b's archive validation/privacy mechanics.

Inspect the validated archive through maintained readers, with private canaries
for exception messages, usernames, paths, remote names and arguments. Keep only
approved fixed fields and provenance. A placeholder reporter exception is not
the original failure, communication completion is not process success, and a
healthy later event cannot erase the failing stage's incident.

## Work sequence

1. Verify the qualified crash mechanism and begin a fresh kiosk attempt with
   recorded renderer/security provenance and exact process ownership.
2. Exercise the owned abnormal exit with no surviving kiosk app; retain the
   original exit/signal evidence before successful reentry.
3. Reenter, freshly collect through the broker and download an actual archive.
   Validate retained crash cause, source completeness and privacy canaries.
4. Retain the independent archive result and finish owned cleanup. A reporter
   placeholder or successful restart cannot replace original crash evidence.

## Validation and close-out

Run affected catalogue, Gio, export, process-lifetime and privacy tests first.
Require this complete installed crash/export history and an actual valid
downloaded export on each target. The timer export and isolated failure
selection retain their own 010b/010a evidence. Preserve bounded
collection/unavailable results, candidate identities and all owned cleanup.
Fix missing causal evidence or failure-isolation defects at their existing
producer/collector boundary; do not attach raw journals or change transport.
Build as required and update existing diagnostic/coverage owners.
