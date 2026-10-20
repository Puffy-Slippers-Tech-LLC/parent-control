# C03b — Reconcile approval and broker host tests

Acceptance: host

Required tasks: C03a.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Audit checked-in and old-plan active tests/component/test_authorization_lifecycle.py and approval/
request/startup/controller unit tests against C02b's full caller chain. Retain
genuine approval, wrong-role/target refusal, cancellation, no stale/duplicate
grant and policy transaction outcomes without asserting discarded receipt shapes.

Port shared mocks once at their owning support layer. Run affected unit and
private-bus component selectors; include overlay callers where shared code
changed. Keep required behavior tests even when the old implementation fixture
must be replaced. Delete obsolete old-plan fixtures and unused mocks instead of
keeping disabled copies. Apply resource review if fixtures change and record dispositions.
