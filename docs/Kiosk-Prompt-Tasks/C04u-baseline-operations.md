# C04u — Qualify baseline entry and approval on Ubuntu

Acceptance: installed
Targets: onpc-Ubuntu26.04

Required tasks: C04b.
Estimate: 30–45 min; session exception: paired entry and real authentication operation.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared live verification](../TestAutomation/E2E-Execution-Contracts.md#live-verification-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

C04b supplies finite selectors, values, expected results and qualification gaps.
Read tests/e2e/kiosk_entry.py, kiosk_approval.py and the actual shared operations
they call. Adapt or renew only the shared passwordless-entry/genuine-approval
operation for the rebuilt candidate. Use the same operation in qualification and
its customer consumers; product controls use the shared UI API and real system
authentication uses its qualified provider adapter.

Register the exact bounded qualification before invoking it. Verify usable
passwordless entry, selected-child/parent association, genuine authentication
and an independent grant result, plus the operation's required cancellation/
identity guards and owned exit/restoration. No C-series test selector is implied.
Extra independent surfaces or compositions require bounded prerequisites before
this consumer; do not absorb C05's full time/app customer journey.

Run affected host checks and the finite installed qualification on Ubuntu using
the VM/UI/storage owners. Record candidate applicability, exact command/timeouts,
qualified scope, retained result and cleanup in catalogue/runner records. Repair
product causes only under review/build gates. This qualifies an operation, not
the baseline customer journey or the Fedora route.
