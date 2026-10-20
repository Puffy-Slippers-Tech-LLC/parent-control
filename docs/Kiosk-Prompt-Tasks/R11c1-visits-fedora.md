# R11c1 — Qualify Fedora visits and renewal

Acceptance: installed
Targets: onpc-Fedora44

Required tasks: R11b — Fedora boundary/policy receipts and candidate identity.
Estimate: 30–45 minutes; refine from R09's measured history timings.

Read the [master D family](../Kiosk-Resilience-Plan.md#acceptance), R09's frozen
visit/renewal map, [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[live/system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

Extract visit/renewal acceptance from R11c. Run the same mapped registered
histories with `--vm onpc-Fedora44`, explicit timeouts, actual GDM and enforcing
SELinux. Cover fresh entry, exit/reentry, ten visits, rapid reentry, healthy reuse,
one stale/failed owned renewal, interrupted renewal and competing login with
live/foreign/replaced-state preservation. Require usable passwordless form and
genuine approval within the original readiness budget; preserve actual caller
credentials, privileged-helper authority and bounded state/descriptor growth.

## Close-out

Retain exact inputs, public results, first failures and owned restoration/cleanup
for R11c/R11. Apply master's repair gates; map shared changes to earlier Fedora
and Ubuntu receipts and schedule invalidated reruns. Close only R11c1. Session
exception: keep each continuous repeated-visit or renewal/interruption/reentry
history, including waits and restoration, in one attempt. Split independent
excess before execution. R11c2 owns approval races, R11c3 cross-child readiness
and R11c transient dependencies.
