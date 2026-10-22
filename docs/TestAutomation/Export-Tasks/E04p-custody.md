# E04p-custody — Implement dependency and retirement custody

Acceptance: host
Requires: E03

## Status and reading route

Frozen future allocation under the [master](../Export-Execution-Plan.md);
until its consumer inserts the frozen block, this is outside the active queue.
Once inserted, execute only when selected; authoring grants no completion.
The [parent consumer](E04-lifetime.md) retains every original assertion and its
close-out obligation after this allocation passes. Shared protocols remain owned
by the [design](../Export-Design.md), not by this brief.
Read [custody protocol](../Export-Design.md#lock-order-dependencies-and-retirement), [consumer declarations](../Export-Design.md#exact-references-and-planned-interfaces), [retirement inventory](../Export-Design.md#retirement-entry-points).
Follow the design maps to complete affected functions and necessary callers;
discover any additional source/test filename before reading it.

## Delivery

Read `tools/test_retention.py` Store/Publication, `tools/test_input_transfer.py`
mutation guards, `tools/plan_evidence.py` preserve/recover and helper custody
callers. Extend the minimal capture catalogue to its full canonical consumers,
captures, reservations and retirements, using exact revisions and lifecycle CAS.
Continuation, suspension, rejected responses and accepted Git retry retain proof;
only authorized lifecycle release or verified replacement discharges it.
Keep privileged root safety witnesses authoritative for every ever-required
source; caller role/release edits or absent catalogue entries cannot discharge it.
Implement whole-set retire prepare/permit/delete/finish with exact progress,
one-use identities and root witness lifetime; no partial audit before deletion.
Acquire no owner, writer, lease, helper or payload I/O under the catalogue lock.

## Finite acceptance

P02 covers all-set identity/dependency/capacity refusal before first deletion,
late consumers blocked by intent, lost replies, partial removal and exact retry.
Abort only before deletion; changed remaining identity refuses without adoption.
Reserve verified replacement before releasing verification scope; independently
reverify privileged replacement immediately before deletion under its reservation.
Missing/replaced replacement refuses despite matching historical ack JSON.
Assert no source/destination lock inversion, no unilateral reservation release
during outstanding source intent, and no gap in working/accepted custody.
E04p-retirement owns integration at every inventoried existing route.

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

