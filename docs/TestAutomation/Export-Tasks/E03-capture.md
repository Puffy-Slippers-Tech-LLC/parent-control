# E03 — Capture evidence before rotation

Acceptance: host
Requires: E02

## Purpose and delivery

Deliver the shared finalized-record handoff from the
[capture design](../Export-Design.md#capture-and-publication), following the
[master](../Export-Execution-Plan.md). Read `test_retention.Store`, allocation/
scratch ownership, `evidence_bundle.Selection`, publication, `plan_evidence`
capture/carry, qualification storage and their callers.

Create bounded working collections through shared allocation. The live owner
explicitly hands off a finite immutable finalized subset and receives a durable
acknowledgement before releasing its source. Bind the owner/attempt and exact
dependency bytes; reject unrelated active allocations and concurrent mutation.
Do not disable finished-owner, independent-publication or inherited-session
guards. Preserve partial/failed/interrupted status and required command, input
and cleanup dependencies; a pre-cleanup record is incomplete, not a pass.
Retain exact working proof across cancellation, restart and suspension, with
identity-bound recovery for unfinished copying/publication.
Apply the master's controller-dependency registration and actual-file restart
checks in this task, including changes to retention/storage or extracted capture
modules. Retain the required-source dependency until durable acknowledgement;
an attempted or failed copy cannot release it to later startup recovery.

## Validation and close-out

Use private fixture journals to test active authorized handoff, foreign owner,
mutating source, missing dependency, cancellation, acknowledgement failure and
interruption at each durable boundary. Reject replayed acknowledgements with a
different attempt, source identity or dependency closure. Continue/restart more
than three times while preserving exact required records and bounded allocation
ownership.
Cover the failed/unacknowledged-capture branch of
[report rotation](../Export-Design.md#required-regression-histories); E04 owns
enforcement at every retirement entry point. Preserve the original bytes and
dependency registration on capacity or acknowledgement refusal.
Extend affected retention, qualification-storage, bundle and plan-evidence safety
tests. Run those explicit safety selections before exercising changed protected
operations. Update the storage/retention owner for delivered behavior and follow
the master's host validation, owned cleanup and close-out.
