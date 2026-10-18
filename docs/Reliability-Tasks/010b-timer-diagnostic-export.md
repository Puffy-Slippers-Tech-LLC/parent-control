# 010b — Timer incident export after recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 002, 004, 009, 010a.
Estimate: 45–75 minutes.
Session exception: reporter lifetime, native failure/recovery, fresh collection
and downloaded archive must retain one causal history per target.

## Deliverable and route

Extract the child-reporter/timer export branch from 010. Read the
[diagnostic contract](../SystemDesign/Logging-and-Feedback.md), child handlers,
dependency collectors, catalogue validators and canonical
`check_e2e_diagnostic_export.py`/host export tests. Reuse 002a/002's shared native
fault mechanics, not their acceptance matrix. Planned qualification
(unimplemented): `check_e2e_timer_failure_diagnostic_recovery`.

Open the child reporter before one reviewed timer failure, retain repeated-failure
evidence, recover timer reads, then perform a fresh normal collection and export
through the existing report owner. Original operation/stage/category must survive
later success and duplicate-window suppression. A snapshot frozen before failure
need not acquire later events; do not mutate snapshot or submission bytes.
Communication completion and placeholder reporter exceptions are not original
process/operation evidence. No feedback submission is required.

Inspect an actual valid downloaded archive through maintained readers, using
private canaries for messages, usernames, paths, remote names and arguments.
Retain only approved fixed fields/provenance and accurately bounded collection
completeness. Reuse canonical archive validation in later consumers.

## Acceptance and close-out

Run affected catalogue/Gio/export/privacy and reporter-lifetime host checks, then
the complete history and actual sanitized export on both targets. Keep first
failure, later recovery, archive validation and owned cleanup receipts. Repair
causal-evidence defects at their existing boundary, build as required and update
existing owners. Close only 010b; dead-kiosk-app export remains in 010.
