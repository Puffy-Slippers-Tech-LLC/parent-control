# E03p-capture — Publish and acknowledge working capture

Acceptance: host
Requires: E03p-auth

## Status and reading route

Frozen future allocation under the [master](../Export-Execution-Plan.md);
until its consumer inserts the frozen block, this is outside the active queue.
Once inserted, execute only when selected; authoring grants no completion.
The [parent consumer](E03-capture.md) retains every original assertion and its
close-out obligation after this allocation passes. Shared protocols remain owned
by the [design](../Export-Design.md), not by this brief.
Read [capture transitions](../Export-Design.md#finalized-capture-authority-and-durable-transitions), [custody ordering](../Export-Design.md#lock-order-dependencies-and-retirement), [capacity](../Export-Design.md#bounded-collections-capacity-and-reuse).
Follow the design maps to complete affected functions and necessary callers;
discover any additional source/test filename before reading it.

## Delivery

Read `tools/evidence_bundle.py` publication/verification, `tools/plan_evidence.py`
capture/carry, `tools/test_retention.py` Publication/recovery and authenticated
`tools/onpc-test-artifacts` dispatch through their complete relevant callers.
Deliver the indivisible publish/index/durable-reservation/acknowledgement/release
transaction, including the minimal canonical capture catalogue required by it.
After E02's strict readers, deliver the initial single-segment v2 working
publication writer and working index before any acknowledgement. E04p-collections
extends this to segmented replacement/compaction and accepted ledger/locator
writers; this delivery does not depend on that future implementation.
Register capture custody helper operations and immutable transaction lookup;
host code uses the same library. Provisional capacity is never verified custody.
Verify publication and index CAS before acknowledging; persist durable replacement
reservation before verification locks release. Source-writer prepare, catalogue
CAS and mirrored result follow the shared nonnested lock protocol.
Never release an original before independently verified exact custody.
Before activating capture, add the all-route fail-closed bridge for every
ever-required source: direct session/count prune, host/privileged reconcile and
the separate privileged prune, publication/explicit retirement, transfer, legacy
and media replacement routes from the complete design inventory must preserve
required sources until E04 delivers their full verified retirement integration.
No new production capture caller may run before that bridge and safety checks pass.

## Finite acceptance

P03/P12 inject crash and cancellation at every required-through-released state,
including committed publication before index, failed CAS, lost replies and stale
attempt/source/closure acknowledgements. Retry the same transaction idempotently.
Assert failed CAS reserves both copies; changed consumer entries refuse while
unrelated catalogue increments do not. Source revalidation failure after CAS
preserves destination custody and refuses instead of silently undoing it.
Include projected/actual old+sealed+new+receipt/recovery limits and failed capacity;
previous proof, original dependencies and same pending slot remain intact.
No pass comes from acknowledgement JSON or failed/pending producer cleanup.
Exercise every bridge route with missing/failed/stale acknowledgement and
unchanged required originals; disposable unreferenced controls keep their
existing cleanup behavior. Assert single-segment working writer/index verification
and exact interrupted recovery without any E04 writer dependency.

## Validation and close-out

These P histories and any new interfaces/selectors remain unimplemented and
unregistered until delivery registers their concrete parsers, tests and contracts.
Discover actual tests, then select the lowest effective maintained host checks
through tools/run-tests help/list; record exact selectors and explicit timeout
before invocation. Run applicable safety selections before changed protected
operations. Follow [test maintenance](../../../tests/README.md) and the
[storage mandate](../../Mandates/Test-Storage-Mandate.md).
Apply the [controller guard](../Export-Design.md#controller-compatibility-guard)
in this introducing task for every new/changed retained-decision dependency,
including actual-file-byte restart coverage before close-out.
Finish [host resource review](../../../tests/README.md#host-test-parallelism-review)
for applicable module/resource inventories; runtime fallback is not review.
Use private fixtures only, clean only their owned identities, preserve unrelated
work and retain exact commands/results/cleanup through shared publication.
Check changed documentation links and update existing owners for delivered rules.
Complete this row only after host acceptance and owned cleanup; the parent
consumer still owns inherited acceptance and final composition obligations.

