# 010b — Timer incident export after recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Master](../Reliability-Plan.md),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract) and
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Required tasks: 002, 010a.
Estimate: 45–75 minutes.
Session exception: reporter lifetime, native failure/recovery, fresh collection
and downloaded archive must retain one causal history per target.

## Deliverable and route

Reproduce `5414b496`/`5b15f17d`'s original-cause retention boundary using one real
timer fault. This does not consume unlock or preference-failure journeys. Read the
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

## Work sequence

1. Verify the native fault/export bindings and open the child reporter before
   the one reviewed timer failure in a fresh attempt.
2. Retain repeated failure and original category evidence, then recover native
   timer reads without replacing the already-open reporter history.
3. Perform a fresh normal collection and actual download. Validate the archive
   through the maintained reader, including causal evidence and privacy canaries.
4. Preserve bounded collection-completeness and owned cleanup receipts. Later
   success or duplicate-window suppression cannot erase the original cause.

## Acceptance and close-out

Run affected catalogue/Gio/export/privacy and reporter-lifetime host checks, then
the complete history and actual sanitized export on both targets. Keep first
failure, later recovery, archive validation and owned cleanup receipts. Repair
causal-evidence defects at their existing boundary, build as required and update
existing owners. Close only 010b; dead-kiosk-app export remains in 010.
