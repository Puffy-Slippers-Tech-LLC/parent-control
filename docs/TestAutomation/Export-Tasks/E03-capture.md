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

## Frozen prerequisite insertion

E01b allocation: 165–225 min total; this consumer's integration and full inherited
acceptance remain 30–45 min after the two deliveries below. The 90–120 min capture
transaction stays indivisible: publication, index, reservation, acknowledgement
and source release must have one crash-safe recovery protocol and safety matrix,
including the initial working writer and all-route fail-closed activation bridge.
The authentication delivery exposes no production caller before that protocol.

When E03 is selected, before implementation insert exactly this contiguous block
immediately before E03; the finite briefs already exist. These are future rows,
not completion or execution by E01b:

Brief navigation: [E03p-auth](E03p-auth.md), [E03p-capture](E03p-capture.md).
The literal rows below use queue-relative destinations; copy them unchanged.

```markdown
| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | E03p-auth | [Authenticate sealed producer handoffs](Export-Tasks/E03p-auth.md) | E02 | Authenticate exact producer attempts and independently finished sealed subsets without reading active mutable owners | 45–60 min |
| [ ] | E03p-capture | [Publish and acknowledge working capture](Export-Tasks/E03p-capture.md) | E03p-auth | Deliver the complete bounded publication, durable custody, acknowledgement and source-release recovery transaction | 90–120 min |
```

Exact E03 Requires before: `E02`; after: `E02, E03p-capture`.
At insertion update this brief's top-level Requires to that same after field.
Both new briefs declare `Acceptance: host`, with no Targets. Preserve E03's
Acceptance, Scope and every assertion above; these deliveries do not close E03.
Use the [shared insertion route](../../Execution-Plans.md#execution-and-delegation)
and [frozen guard checks](../Export-Design.md#frozen-insertion-guard-review).
Keep all existing completion/order/rows fixed, finish owned cleanup, point the
master to E03p-auth and return `prerequisite_required` (or a valid `continue`)
with the retained consumer handoff. Never edit a checkpoint or run a prerequisite
in the insertion session. After resumption, compose real handoff/carry across
suspension/restart and verify every original E03 assertion before close-out.
