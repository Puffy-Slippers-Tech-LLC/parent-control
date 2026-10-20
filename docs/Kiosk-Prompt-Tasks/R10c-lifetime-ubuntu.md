# R10c — Qualify Ubuntu transient recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04

Required tasks: R10b — boundary/policy receipts; R10c1 — visits/renewal;
R10c2 — approval lifetime; R10c3 — cross-child readiness.
Estimate: 20–30 minutes; refine from R09's complete-history timings.

Read the [master D/E families](../Kiosk-Resilience-Plan.md#acceptance), R09's map,
[live contract](../TestAutomation/E2E-Execution-Contracts.md#live-verification-contract),
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

R10c1 extracts visits/renewal, R10c2 approval races and R10c3 cross-child readiness.
Use their applicable public results and cleanup receipts; cumulative D/E acceptance
remains required. This task runs the remaining E service/bus/lock recovery and
permanent-global-failure controls through actual GDM/AppArmor.

Inspect maintained inventory; run mapped registered selectors with
`--vm onpc-Ubuntu26.04` and explicit timeouts. Exercise bounded AccountsService/
broker/session-bus delays or restarts and lock contention through recovery,
usable passwordless entry and genuine approval within the original budget.
Retain the first cause and required enforcement. Test permanent global failure
separately: accurate unavailable-operation/retry/exit is required and supplies
no positive usable-request pass. Keep every fault/recovery/reentry/restoration
history complete in one attempt.

## Close-out

Retain candidate/input/results, first failures and full owned restoration/cleanup.
Apply master repair gates; rerun invalidated complete histories and map implications
for earlier Ubuntu receipts. Reconcile R10c1–R10c3 to the same final D/E input map;
do not rerun unchanged histories to aggregate evidence. Close only R10c. Extract
independent additional histories before execution if measured timing exceeds the
allowance; any indivisible wait/recovery exception must name that exact history.
