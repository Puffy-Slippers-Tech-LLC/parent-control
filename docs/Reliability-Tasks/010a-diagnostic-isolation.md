# 010a — Diagnostic failure isolation

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract diagnostic writer/transport failure isolation from 010. Read the
[diagnostic contract](../SystemDesign/Logging-and-Feedback.md), child refresh/lock
and process-exit producers, catalogue validators and complete relevant host
export/process-lifetime tests. Reuse canonical fault adapters and collection
owners; no feedback submission or external message is involved.

At successful refresh, lock and cleanup boundaries, fail only the diagnostic
writer or transport. The underlying operation keeps its independently observed
result; failure neither throws into the caller nor creates a recovery loop or
leaks owned callbacks/processes. Retain the original operation/stage/category
where collection remains available, and accurately report unavailable evidence
otherwise. Healthy unrelated events cannot clear the failing stage's incident.
Use private exception, username, path, remote-name and argument canaries; only
approved fixed fields/provenance may escape.

## Acceptance and close-out

Run exact affected unit/component and child-node/GJS selections through
`tools/run-tests`, with explicit timeouts. Assert operation results, bounded
report attempts, causal category and privacy independently of logging callbacks.
Fix demonstrated producer/collector isolation defects, review resources, build
as required and retain runner evidence/cleanup. Close only 010a. Actual native
failure exports remain in 010b/010.
