# R01c — Settle approval and visit lifetime

Acceptance: review

Required tasks: R01a — execution boundary; R01b — effective authentication route.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md),
[Broker lifetime decision](../SystemDesign/Broker.md#prospective-kiosk-approval-lifetime),
[specification](../Specification.md#requesting-and-approving-access)
and [execution contract](../Execution-Plans.md#execution-and-delegation).

## Session boundary and route

Extract request/agent/session identity and cancellation/commit ordering from R01.
Read complete `_PendingAuthorization.run()`, `_request_access()` and necessary
identity, session, agent, usage-query and transaction callers/callees. Follow the
sessionless/primary-display fallback, not just bus-name liveness. R01e owns
infrastructure recovery; R06 later composes approval lifetime with it.

## Deliverable and acceptance

Choose a concrete association of originating visit, request, process/bus identity,
agent, target, approver and exact logind session across reuse/renewal and competing
visits. Preserve pending-authentication cancellation. Settle with Specification/
Broker owners the externally visible point after which an approved original
request may complete, including post-authentication usage queries and irreversible
effects. A late result cannot revive cancellation or authorize another visit.
Do not change grant arithmetic or transaction rollback semantics.

Record the decision in those existing owners and the single ledger before R02a.
Define both event orderings using a delayed usage query, session switch/exit and
reentry; observe original grant outcomes independently of the prompt, then require
a fresh request to succeed. R01 independently reviews the integrated architecture;
this task implements no broker changes or expectation rewrites. Check links and
documentation consistency, preserve historical evidence and leave no runtime state.
