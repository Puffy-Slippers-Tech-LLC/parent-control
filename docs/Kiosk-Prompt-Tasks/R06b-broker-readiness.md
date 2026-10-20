# R06b — Isolate broker readiness by affected child

Acceptance: host

Required tasks: R06a — bounded lifecycle recovery and deadline.
Estimate: 90–150 minutes; [R01 mechanism estimate](../SystemDesign/Kiosk-Confinement.md#implementation-estimates-after-integrated-review).
Size independent work before execution; this forecast does not expand the session exception or reduce acceptance.

Read the [master](../Kiosk-Resilience-Plan.md#allow-recover-and-reject), accepted
readiness decision, [prerequisite classification and finite A/B control](../SystemDesign/Lifecycle.md#audited-readiness-path-and-prerequisite-classes),
[shared deadline](../SystemDesign/Lifecycle.md#one-measured-entry-and-recovery-budget)
and [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract the cross-account startup repair from R06. Read complete service
construction through D-Bus registration, `Service._start_policy()`,
`Broker.refresh_enabled_extensions()`, `ExtensionManager.set_enabled()` and
necessary account/configuration/failure callers. Implement R01's finite
classification and bounded recovery so child A's unavailable home/extension
does not prevent a genuine approved request for healthy child B. The finite
control makes A unavailable before startup with no live A session. Retain live
activation/rollback checks and accurate failure reporting; this work selects no
new degraded live-enforcement state or forced-logout policy.

Preserve required enforcement and actionable unavailable-operation reporting for
A; restore A and verify recovery. Separate an actual global enforcement failure
from another child's unavailable integration. Never silently skip enforcement,
disable the entire broker without a concrete dependency, restart the deadline
or broaden this into a general broker rewrite. R06 owns approval identity races.

## Acceptance and close-out

Run affected maintained broker/startup host checks for A unavailable/B successful,
A restoration, bounded retries and permanent global failure. Keep original-cause
diagnostics and no-PII assertions. Require master product review/revision and
`make build` after final packaged changes; update existing owners and provide
exact candidate/selectors to R06/R09b3. Complete owned cleanup. Installed E
requires actual healthy-child approval, not just D-Bus registration or an error UI.
