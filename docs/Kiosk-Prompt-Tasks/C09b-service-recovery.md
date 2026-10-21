# C09b — Bound required-service recovery

Acceptance: host

Required tasks: C09a1f.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Trace actual broker/frontend shared-service readiness callers. Address
demonstrated gaps only: finite recovery of a transient required service and safe
retry/exit when genuinely unavailable. Preserve all required enforcement; an
empty policy or false approval is never a fallback. Per-child isolation belongs
to C09b1.

Human decisions are not machine work; retries cannot reset deadlines forever.
Retain the first sanitized cause in the existing diagnostic path. Add targeted
host tests and exact complete installed fault/restoration/reentry bindings,
including the real Parent diagnostic download after recovery.
Require independent backend review, affected checks and final build.
