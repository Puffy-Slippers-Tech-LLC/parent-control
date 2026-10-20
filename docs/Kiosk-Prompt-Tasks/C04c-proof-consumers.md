# C04c — Reconcile obsolete proof and design consumers

Acceptance: reconciliation

Required tasks: C04f.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

Reconcile the cumulative source/test dispositions with Kiosk-Confinement-Proof,
confinement/lifecycle design, the specification's prospective kiosk-visit section,
Reliability-Plan and its unfinished kiosk consumers, and E2E catalogue/recipes.
Inspect both committed text and active changes originating in the old plan.
Historical evidence retains its exact claims without becoming replacement
acceptance or a hidden native-receipt/private-view obligation.

Remove obsolete prospective mechanisms, unused briefs and dead helper references.
Move surviving required behavior to its owner; preserve current implementation
descriptions only when they still match the rebuilt source. Do not preserve
legacy prose as an alternative execution plan. Resolve conflicting future
visit/timeout clocks against usability and human-pause requirements without
weakening genuine approval/cancellation behavior.

Check changed links and incoming anchors, plan/inventory/composition consistency
and coverage when its source changes. Record remaining baseline qualification
gaps for C04. Reconciliation grants no product or installed acceptance and
closes no row of the separate reliability/E2E plans.
