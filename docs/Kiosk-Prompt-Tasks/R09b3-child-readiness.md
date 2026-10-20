# R09b3 — Compose cross-child readiness histories

Acceptance: host

Required tasks: R09b2 — shared approval/result and session-history composition.
Estimate: 15–30 minutes.

Read the [master E family](../Kiosk-Resilience-Plan.md#acceptance), R06b's
delivered per-child readiness/recovery interfaces, [lifecycle owner](../SystemDesign/Lifecycle.md#prospective-configuration-and-activation-recovery),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [composition preflight](../TestAutomation/E2E-Building-Blocks.md#composition-preflight).

## Session boundary and deliverable

Extract cross-child broker startup isolation from R09b. Read complete maintained
home/extension fixture, broker-start, genuine approval and restoration callers.
Register unavailable-home child A at broker startup while healthy child B
completes a genuine approved request; restore A and verify its recovery and
required enforcement. Retain A's actionable first cause and the original deadline.
Do not silently skip enforcement or infer healthy B's availability from a running
broker. Bind any R06b-selected extension branch to its finite declared fixture.
R09b owns transient global dependencies and the permanent-global-failure control.

## Acceptance and close-out

Run scoped host composition/registration, account-isolation and complete
restoration checks under resource/storage contracts. Record registered selectors,
account roles, expected public results, enforcement observations and cleanup for
R09 and R10c3/R11c3. Planned selectors remain unimplemented. Apply master's repair
gates if needed; finish cleanup. No VM acceptance or broader storage campaign occurs.
