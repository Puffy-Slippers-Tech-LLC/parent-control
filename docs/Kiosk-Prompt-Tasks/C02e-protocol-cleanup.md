# C02e — Remove obsolete feature protocols and wiring

Acceptance: host

Required tasks: C02d.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

Use C02d's runtime dispositions and C01's complete frontend/broker caller map.
Delete obsolete confinement-only controller/visit/receipt interfaces, D-Bus
members, imports and residual build/install/removal definitions after proving
their behavior is retained by the selected owner. Cover both checked-in code
and old-plan active additions. Classify by actual function; keep useful current
feature code even in a mixed-purpose new module.

Remove unused adapters and generated-input definitions instead of leaving legacy
or garbage code for later. Preserve caller authorization, genuine approval,
cancellation, policy transactions and shared-overlay features. Retention records
and installed-state migration remain owned, not arbitrary deletion targets.

Repair directly affected tests/registrations, run focused host checks, independent
backend review and final make build. Close the cumulative source removal map:
every committed/active item has a retained owner or verified removal and no
discarded framework is selected or hidden in production/tests. C03 audits
remaining automation; it is not a license to leave broken dependencies.
