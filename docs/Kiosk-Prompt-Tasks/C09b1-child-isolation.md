# C09b1 — Isolate an unavailable child's integration

Acceptance: host

Required tasks: C09b.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Read the actual broker service/core and extension-integration callers. Address
only demonstrated cross-child readiness coupling: one unavailable child's
integration cannot veto requests and genuine approval for a healthy child.
Preserve the unavailable child's policy and explicit unavailable result where
its required enforcement cannot work; do not silently omit the child or use an
empty policy.

Add targeted host tests and the complete unavailable-child/healthy-child/
restored-child installed binding. Preserve identity and owned cleanup, and use
existing shared operations. New reusable automation needs installed qualification
before consumption. Run affected checks, independent backend review and final
build for product changes. Hand exact finite faults and controls to C10.
