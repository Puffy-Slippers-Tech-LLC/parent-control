# E04p-collections — Implement bounded collection replacement

Acceptance: host
Requires: E04p-custody

## Status and reading route

Frozen future allocation under the [master](../Export-Execution-Plan.md);
until its consumer inserts the frozen block, this is outside the active queue.
Once inserted, execute only when selected; authoring grants no completion.
The [parent consumer](E04-lifetime.md) retains every original assertion and its
close-out obligation after this allocation passes. Shared protocols remain owned
by the [design](../Export-Design.md), not by this brief.
Read [collection layout and budgets](../Export-Design.md#bounded-collections-capacity-and-reuse), [ledger/index schema](../Export-Design.md#canonical-identities-and-wire-records), [capture ordering](../Export-Design.md#capture-and-publication).
Follow the design maps to complete affected functions and necessary callers;
discover any additional source/test filename before reading it.

## Delivery

Read `tools/evidence_bundle.py` verified manifests/receipts and export/recovery,
`tools/plan_evidence.py` cumulative ledger/locator and `tools/test_retention.py`
publication admission, accounting and retirement with shared storage allocation.
Reuse E02's strict v2 readers and E03p-capture's initial single-segment working
writer/index. Deliver accepted ledger/locator writers and extend the working
index to at most three immutable segments in the same generation/allocation.
Never defer the initial working capture writer to this later allocation.
Keep a record's full required closure in one segment, stable logical identities
and all provenance when equal bytes deduplicate; refuse a fourth segment.
Compaction publishes a complete replacement without in-place mutation, nesting,
hardlinks, writable shared payload or another owner journal per segment.
Preserve all existing byte, entry, manifest, depth, selection and read bounds.

## Finite acceptance

P12 measures old+sealed+preparing+committed-unretired+receipts/indexes+recovery
and projected copy overhead by unique physical identity and parent charges.
Reserve before stage creation; compare actual use before commit; pending intent
cannot consume another slot. Cross-owner copies count physically on both sides.
Exercise near byte/file/metadata limits, interrupted append/compaction/index CAS,
missing segment, different same-basename origins and retained consumer closure.
Assert old proof survives insufficient old+new capacity and recorded recovery
reuses its reservation; no silently dropped members or multiplied budgets.
Only explicitly released unreferenced material can disappear in replacement.

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

