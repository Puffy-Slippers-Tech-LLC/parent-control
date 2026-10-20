# R11c2 — Qualify Fedora approval lifetime

Acceptance: installed
Targets: onpc-Fedora44

Required tasks: R11c1 — Fedora visit/reentry receipts and candidate identity.
Estimate: 20–30 minutes; refine from R09's complete-history timings.

Read the [master D family](../Kiosk-Resilience-Plan.md#acceptance), R09's approval
map, accepted [commit ordering](../SystemDesign/Broker.md#prospective-kiosk-approval-lifetime),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[live/system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

Extract approval lifetime from R11c. Run the same mapped registered selectors
with `--vm onpc-Fedora44`, explicit timeouts, actual GDM and enforcing SELinux.
Pending authentication followed by switch/exit/reentry grants nothing late,
adopts no old prompt and allows a fresh successful request. Exercise both accepted
approval/commit orderings with delayed post-authentication usage; observe the
original request's grant independently of the prompt. Preserve the genuine
privileged authentication helper. Keep each ordering's transition, result,
fresh approval and restoration together; label injected delay as engineering control.

## Close-out

Retain exact inputs, event orders, public results, first failures and owned cleanup
for R11c/R11. Apply master's repair gates; map shared changes to all affected
Fedora/Ubuntu receipts and schedule invalidated complete-history reruns. Close
only R11c2; no transient or cross-child result is accepted here.
