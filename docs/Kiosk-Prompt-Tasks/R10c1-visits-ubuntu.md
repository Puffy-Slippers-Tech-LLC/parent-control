# R10c1 — Qualify Ubuntu visits and renewal

Acceptance: installed
Targets: onpc-Ubuntu26.04

Required tasks: R10b — Ubuntu boundary/policy receipts and candidate identity.
Estimate: 30–45 minutes; refine from R09's measured history timings.

Read the [master D family](../Kiosk-Resilience-Plan.md#acceptance), R09's frozen
visit/renewal map, [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[live/system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

Extract visit/renewal acceptance from R10c. Inspect runner help/inventory and run
the mapped registered histories with `--vm onpc-Ubuntu26.04` and explicit timeouts
through actual GDM/AppArmor. Cover fresh entry, exit/reentry, ten sequential visits,
rapid reentry, healthy reuse, one stale/failed owned renewal, interrupted renewal
and competing login with live/foreign/replaced-state preservation. Require usable
passwordless form and genuine approval within the original readiness budget;
preserve actual caller credentials and bounded state/descriptor growth.

## Close-out

Retain exact candidate/fixture inputs, public results, first failures and owned
restoration/cleanup for R10c/R10. Apply master's product-repair gates and rerun
invalidated complete histories, mapping changes to earlier Ubuntu receipts.
Close only R10c1. Session exception: retain each continuous repeated-visit or
renewal/interruption/reentry history, including waits and restoration, in one
attempt. Split independent excess scope before execution; R10c2 owns approval
races, R10c3 cross-child readiness and R10c transient dependencies.
