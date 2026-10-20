# R11c — Qualify Fedora transient recovery

Acceptance: installed
Targets: onpc-Fedora44

Required tasks: R11b — boundary/policy receipts; R11c1 — visits/renewal;
R11c2 — approval lifetime; R11c3 — cross-child readiness.
Estimate: 20–30 minutes; refine from R09's complete-history timings.

Read the [master D/E families](../Kiosk-Resilience-Plan.md#acceptance), R09's map,
[live contract](../TestAutomation/E2E-Execution-Contracts.md#live-verification-contract),
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

R11c1 extracts visits/renewal, R11c2 approval races and R11c3 cross-child readiness.
Reuse applicable public results and cleanup receipts; cumulative D/E acceptance
remains required. This task runs E's remaining service/bus/lock recovery and
permanent-global-failure controls through actual GDM and enforcing SELinux.

Inspect maintained inventory and use mapped registered selectors with
`--vm onpc-Fedora44` and explicit timeouts. Cover bounded AccountsService/broker/
session-bus delays or restarts and lock contention through recovery, usable
passwordless entry and genuine approval within the original deadline. Preserve
enforcement, first cause and actual helper authority. Test permanent global
failure separately: accurate unavailable-operation/retry/exit supplies no usable-
request pass. Keep each fault/recovery/reentry/restoration history in one attempt.

## Close-out

Retain exact inputs/public results, first failures and complete owned restoration/
cleanup. Apply master repair gates; map changes to earlier Fedora/Ubuntu receipts
and schedule invalidated reruns. Reconcile R11c1–R11c3 to the final D/E input map
without repeating unchanged histories merely to aggregate evidence. Close only
R11c. Split independent excess before execution; any indivisible wait/recovery
exception must name its exact history and measured allowance.
