# R02a — Implement the minimal startup transaction

Acceptance: host

Required tasks: R01 — independently reviewed architecture and ledger.
Estimate: 30–60 minutes.

Read the [master](../Kiosk-Resilience-Plan.md#acceptance), accepted design/ledger,
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and complete native/policy/session/packaging callers selected by R01.

## Session boundary and deliverable

Extract the runnable transaction from R02. Implement one smallest intended
production path: owned account, dedicated session, actual execution boundary,
compositor/request form, genuine parent approval, Cancel/exit/reentry and one
bounded owned renewal. Use R01's authentication, activation and request/agent/
visit association, including its accepted approval lifetime mechanism. R06 later
completes recovery/race composition. Create no second sandbox engine, unrestricted
fallback or replacement remote-control API.

Provide actual GDM/manager credential-order, enforcing-policy, first-exec,
pre-boundary-child and open/setcred/close teardown witnesses. Reuse existing
private native/PAM probes and public station operations. Preserve permitted
controls for alternate-desktop/SSH and reachable launch barriers. R02b/R02c own
the two unfamiliar integration fixtures; R02 owns complete proof composition.

## Acceptance and close-out

Run registered affected native/PAM/preparation/session/package host checks,
including actual production-call composition, cancellation and owned failure
cleanup. Record test-double limits; host success grants no installed proof.
Apply resource review and the master's mandatory product review/revision, then
`make build` after the final packaged edit. Update existing design limits and
record exact candidate/callable inputs for fixture consumers. Complete owned
cleanup. Session exception: the execution boundary, caller credentials and failure
cleanup are one native transaction; independent fixtures/composition are extracted.
