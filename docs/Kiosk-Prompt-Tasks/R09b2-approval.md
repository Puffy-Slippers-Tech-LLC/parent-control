# R09b2 — Compose approval lifetime histories

Acceptance: host

Required tasks: R09b1 — registered visit/reentry and identity-observation mechanics.
Estimate: 20–30 minutes.

Read the [master D family](../Kiosk-Resilience-Plan.md#acceptance), accepted
[approval/commit contract](../SystemDesign/Broker.md#prospective-kiosk-approval-lifetime),
R06's delivered association/cancellation interfaces, [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [composition preflight](../TestAutomation/E2E-Building-Blocks.md#composition-preflight).

## Session boundary and deliverable

Extract approval races from R09b. Read complete shared approval, delayed-usage,
session-transition and independent grant-observer callers. Register pending
authentication followed by switch/exit/reentry: the late result grants nothing,
the new visit adopts no old prompt, and a fresh request succeeds.

Register both accepted post-authentication approval/commit event orderings using
the delayed usage query. Observe the original request's grant independently of
the displayed prompt; assert R01's chosen cancellation boundary without changing
grant arithmetic or rollback semantics. Keep each ordering's request, transition,
late result, fresh approval and restoration in one history. Infrastructure
renewal mechanics remain R09b1; cross-child and transient controls have other owners.

## Acceptance and close-out

Run finite host ordering/composition/registration and restoration checks using
delivered operations. Identify injected delay as engineering control and public
grant outcomes separately. Record exact selectors, event orders, inputs and
cleanup for R09 and R10c2/R11c2; planned names are not runnable. Apply resource
review and master repair gates as needed. Finish cleanup; no VM acceptance occurs.
