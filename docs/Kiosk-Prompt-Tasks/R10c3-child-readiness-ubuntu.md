# R10c3 — Qualify Ubuntu cross-child readiness

Acceptance: installed
Targets: onpc-Ubuntu26.04

Required tasks: R10c2 — Ubuntu approval-lifetime receipts and candidate identity.
Estimate: 20–30 minutes; refine from R09's complete-history timings.

Read the [master E family](../Kiosk-Resilience-Plan.md#acceptance), R09's
cross-child map, R06b's delivered enforcement/recovery boundary,
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[live/system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

Extract cross-child readiness from R10c. Use mapped registered histories,
`--vm onpc-Ubuntu26.04`, explicit timeouts and actual GDM/AppArmor. Make child A's
home unavailable at broker startup while healthy B completes a genuine approved
request. Restore A and verify its recovery and required enforcement, including
any finite extension branch declared by R09. Preserve the original deadline and
A's actionable first cause. A running broker, error-only surface or skipped
enforcement cannot supply the positive result. Keep fault, B's request, A's
restoration/recovery and owned cleanup in the same complete history.

## Close-out

Retain exact candidate/account/fixture inputs, independent public and enforcement
results, first failures and restoration for R10c/R10. Apply master's repair gates;
rerun invalidated histories and map earlier Ubuntu applicability. Close only
R10c3; R10c owns service/bus/lock and permanent-global-failure controls.
