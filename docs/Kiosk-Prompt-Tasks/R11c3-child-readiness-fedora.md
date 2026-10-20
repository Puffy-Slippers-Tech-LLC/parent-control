# R11c3 — Qualify Fedora cross-child readiness

Acceptance: installed
Targets: onpc-Fedora44

Required tasks: R11c2 — Fedora approval-lifetime receipts and candidate identity.
Estimate: 20–30 minutes; refine from R09's complete-history timings.

Read the [master E family](../Kiosk-Resilience-Plan.md#acceptance), R09's
cross-child map, R06b's delivered enforcement/recovery boundary,
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[live/system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

Extract cross-child readiness from R11c. Use the same mapped registered histories,
`--vm onpc-Fedora44`, explicit timeouts, actual GDM and enforcing SELinux.
Make child A's home unavailable at broker startup while healthy B completes a
genuine approved request; restore A and verify recovery and required enforcement,
including any finite extension branch declared by R09. Preserve the original
deadline, A's first cause and actual authentication-helper authority. A running
broker, error-only surface or skipped enforcement is no positive result. Keep
fault, B's approval, restored A's recovery and owned cleanup in one history.

## Close-out

Retain exact candidate/account/fixture inputs, public/enforcement results, first
failures and restoration for R11c/R11. Apply master's repair gates; map shared
changes to earlier Fedora/Ubuntu evidence and schedule invalidated reruns.
Close only R11c3; R11c owns global transient and permanent-failure controls.
