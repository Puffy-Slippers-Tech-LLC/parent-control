# E08p-capacity — Keep cumulative capture publication usable

Acceptance: host
Requires: E07a

## Purpose and scope

Remove the discovered publication prerequisite for [E08](E08-markdown.md),
following the [master](../Export-Execution-Plan.md#delivery),
[capture contract](../../../tests/README.md#sealed-producer-handoffs) and
[storage mandate](../../Mandates/Test-Storage-Mandate.md).
Separate a finite per-call capture selection from its accumulated authenticated
publication history. Keep the existing shared metadata, manifest, file, byte and
retention bounds, exact original records, dependency closures, receipts,
acknowledgements and retirement guards. Preserve every prior result and all
currently sealed E08 evidence. Do not reset journals, discard proof, create a
replacement namespace or weaken validation to admit this run.

At discovery, the regression workflow had 253 published requests. E08's new
seven-record publication failed the hardcoded cumulative `<= 256` check in
`capture_publication._validate`, although its own selection was finite. The
published generation remained intact with no pending publication generation;
the finished runner retained its unacknowledged sealed originals.

## Exact reading and implementation routes

Read the applicable contracts above, then these existing owners and necessary
callers: `tools/capture_publication.py` (`_validate`, `_save`, `publish`, delivery
verification), `tools/evidence_bundle.py` (capture selection and cumulative
publication), `tools/evidence_capture.py` (selection bounds, requests and source
acknowledgement), `tools/runner_evidence.py` (terminal finalization and recovery)
and `tools/test_recovery.py` (maintained host recovery).
Reuse existing coverage in `tests/unit/test_evidence_capture.py`,
`tests/unit/test_evidence_bundle.py` and `tests/unit/test_runner_evidence.py`;
discover any other source/test filename before reading it under
[source discovery](../../Approval-Tools.md#source-discovery-before-reads).
New regression cases below are planned behavior, not existing case selectors.

Retained failed publication:
[623 passing executions](../../../output/test-runs/host/reports/20261022T230339Z-448ceedb/report.md),
with exact commands and case inventories in that report directory. The previous
publication is recorded in
`output/test-runs/host/plans/37df86b6d88f8244c3029b1eb10ddce3f89f931e44c7c381b630f957836a75b5/evidence/retention/capture-publication.json`.
Inspect it read-only; the maintained host recovery owns mutations. All spawned
E08 helpers and runner processes ended, and its test fixtures completed cleanup.
Durable original evidence remains protected for recovery, not disposal.

## Current checkout repair

`capture_publication._validate` now bounds cumulative requests with the existing
shared collection/metadata limits, independently of the unchanged per-call
256-input selection limit. Maintained runner startup recovered the original
seven captures into the 260-request cumulative publication and acknowledged them
under their original source owner. A subsequent ordinary publication succeeded
with complete cleanup after [468 focused passing cases](../../../output/test-runs/host/reports/20261022T232745Z-4a0f1ae5/report.md)
in `test_evidence_capture.py`, `test_evidence_bundle.py` and `test_plan_evidence.py`,
using the required 600s timeout. Coverage includes 257 accumulated requests,
same-allocation interruption recovery, exact old/new member reads and oversized
single-call refusal.
The maintained host consistency selection plus `test_regression_unit.py` passed
[342 cases](../../../output/test-runs/host/reports/20261022T233818Z-6d987cce/report.md)
with the same 600s timeout. Generated coverage, changed Markdown links and the
master's `--check` also passed.

The shared bundle reader also accepts registered idle runner-session evidence;
the export controller had stopped while preserving E08's explicit session-log
references. Session journal/worker leases, target scope, archive provenance and
replacement refusals are covered, including prerequisite turns after rotation.
The original `6d1b0c23690d41e9abece7f494a2282c/output` has since rotated; the
maintained reader now reports that exact path as renewable `evidence_unavailable`,
preserving the rejected result without manufacturing its missing diagnostic.
These repairs do not complete E08 or advance the ordinary-plan queue.

## Finite validation and close-out

At the shared publication owner, cover accumulation across the old history
boundary using multiple individually valid selections, exact old/new member
resolution and retry after interruption. Preserve per-selection refusal and
existing metadata/budget, authority, integrity and acknowledgement protections.
Reuse the existing safety matrix rather than multiplying every consumer.
Register and run the lowest affected host selection with an explicit 600s
timeout, resource review and applicable actual-byte controller restart guards.
No VM, installation or product acceptance belongs here.

After repair, use maintained host recovery (`tools/cleanup-e2e --host-only`)
to finish the exact retained terminal capture without changing its original
attempt, inputs, passing verdict or cleanup record. Verify the old cumulative
proof and all new required members remain readable through authenticated
references, and that a subsequent ordinary runner publication succeeds.
Recovery itself grants no E08 completion. Return E08 to acceptance after this
prerequisite passes, renewing only input-invalidated checks.

Check changed Markdown and the master with `--check`; run the maintained
[host consistency selection](../E2E-Execution-Contracts.md#completion-and-document-cleanup).
Finish owned cleanup, check only this prerequisite row, advance the pointer to
E08 and retire this temporary brief after its enduring context is maintained.
