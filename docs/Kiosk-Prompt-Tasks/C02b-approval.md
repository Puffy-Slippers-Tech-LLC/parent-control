# C02b — Separate approval and features from obsolete confinement

Acceptance: host

Required tasks: C02b1.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

C02b1 supplies the coherent broker boundary. This slice adapts its frontend and
agent consumers in kiosk main/controller/startup/agent_locale, preserving shared
child-overlay behavior. Read complete D-Bus callers and the broker interface
contract; do not repeat its implementation migration. Use C01's mapping of
committed code and old-plan active changes to remove obsolete startup/view/
receipt coupling and connect the release-based session interface.

Preserve caller/target validation, genuine selected-parent authentication,
pending-request cancellation, no stale or duplicate grant, policy transactions
and shared-overlay semantics. Human language/password pauses and optional
presentation cannot become admission clocks. Do not delete behavior merely
because its current implementation uses a visit token.

Keep producer and consumers coherent with the still-selected runtime. This task
may land independently compatible frontend/broker decoupling, but cannot switch
confinement activation. Prepare incompatible replacement interfaces without
selecting them; C02 owns that switch and removes any temporary compatibility
live adapter. C02e deletes now-unused feature/protocol modules. Port directly
affected unit/UI fixtures as needed. New product strings require all supported
languages. Independent backend Astra xHigh review, affected tests and final build
are required. Leave no dangling D-Bus caller for C03 to repair.
