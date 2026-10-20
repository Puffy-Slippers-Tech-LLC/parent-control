# R10c2 — Qualify Ubuntu approval lifetime

Acceptance: installed
Targets: onpc-Ubuntu26.04

Required tasks: R10c1 — Ubuntu visit/reentry receipts and candidate identity.
Estimate: 20–30 minutes; refine from R09's complete-history timings.

Read the [master D family](../Kiosk-Resilience-Plan.md#acceptance), R09's approval
map, accepted [commit ordering](../SystemDesign/Broker.md#prospective-kiosk-approval-lifetime),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[live/system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

Extract approval lifetime from R10c. Run mapped registered selectors with
`--vm onpc-Ubuntu26.04` and explicit timeouts through actual GDM/AppArmor.
Pending authentication followed by switch/exit/reentry must grant nothing late,
adopt no old prompt and allow a fresh successful request. Exercise both accepted
approval/commit orderings with delayed post-authentication usage. Observe the
original request's grant independently of the prompt and assert the accepted
boundary. Keep each request/transition/late result/fresh approval/restoration
history complete; injected delay supplies only its engineering claim.

## Close-out

Retain exact inputs, event orders, public results, first failures and owned cleanup
for R10c/R10. Apply master's repair gates, rerun affected complete histories and
map changes to earlier Ubuntu receipts. Close only R10c2; prerequisite visit
evidence is reusable and no transient/cross-child result is accepted here.
