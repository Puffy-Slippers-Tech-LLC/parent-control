# E03p-auth — Authenticate sealed producer handoffs

Acceptance: host
Requires: E02

## Status and reading route

Frozen future allocation under the [master](../Export-Execution-Plan.md);
until its consumer inserts the frozen block, this is outside the active queue.
Once inserted, execute only when selected; authoring grants no completion.
The [parent consumer](E03-capture.md) retains every original assertion and its
close-out obligation after this allocation passes. Shared protocols remain owned
by the [design](../Export-Design.md), not by this brief.
Read [finalized authority](../Export-Design.md#finalized-capture-authority-and-durable-transitions), [wire records](../Export-Design.md#canonical-identities-and-wire-records), [producer map](../Export-Design.md#producer-and-consumer-inventory).
Follow the design maps to complete affected functions and necessary callers;
discover any additional source/test filename before reading it.

## Delivery

Read complete `tools/test_activity.py` producer ownership and session callers,
`tools/test_retention.py` owner/allocation state, `tools/test_storage.py`
allocation admission and `tools/onpc-test-artifacts` authenticated dispatch.
Deliver the opaque session handle bound to held descriptor, journal, run and
issued attempt; paths, environment, nonce or supplied UID cannot mint authority.
Register one disjoint sealed subowner/slot before copying and mark it readable
only after its independent finished-owner commit. Never inspect arbitrary active
parent payloads; preserve finished-owner and independent-publication guards.
Bind the exact finalized allowlist, original/sealed provenance, identities and
before/after digests. Root-required sources gain their private safety witness
before caller catalogue registration. Charge every slot to its parent budget.

## Finite acceptance

P03 covers required/sealing/sealed states: authentic finished handoff succeeds;
missing, pending, foreign, replaced or active registrations and mutated files refuse.
Exercise missing dependencies, wrong attempt/target/request, replay and capacity
refusal without source release, leaked slots or changed prior proof.
Interruption/cancellation retains the same intent and exact resumable stage;
no new capture ID, extra retention allowance or diagnostic promotion.
Register planned finalize/capture selection authentication and helper capabilities
before use; E03p-capture owns publication, acknowledgement and release.

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

