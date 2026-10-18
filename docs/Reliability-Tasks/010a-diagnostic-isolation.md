# 010a — Diagnostic failure isolation

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: 010c.
Estimate: 15–30 minutes.

## Session boundary

Deliver app process-exit/collector cleanup isolation from diagnostic failure.
010c supplies child refresh/lock isolation; this row's cumulative scope retains
those outcomes without repeating the child producer matrix.

## Deliverable and route

Read the [diagnostic contract](../SystemDesign/Logging-and-Feedback.md), complete
process-exit producers, collector/cleanup callers, catalogue validators and
relevant host export/process-lifetime tests. Reuse canonical fault adapters and
collection owners; no feedback submission or external message is involved.

## Work sequence

1. Map existing process-exit/collector isolation checks. At an owned exit or
   cleanup boundary, fail only the diagnostic writer or transport using its
   canonical host adapter; preserve the actual original process outcome.
2. Independently observe completion of owned cleanup despite diagnostic failure:
   no exception into the caller, recovery loop or leaked process/callback.
3. Retain original operation/stage/category and exit provenance where collection
   remains available; accurately report unavailable evidence otherwise. Healthy
   unrelated events cannot clear the failing stage's incident. Use private
   exception, username, path, remote-name and argument canaries; only catalogue
   fields/provenance may escape.
4. Run exact affected unit/component export/process-lifetime selections through
   `tools/run-tests`, with explicit timeouts. Repair demonstrated isolation
   defects and rerun affected 010c child branches if shared inputs change.

## Acceptance and close-out

Run exact affected unit/component selections through `tools/run-tests`, with
explicit timeouts; include affected 010c child checks when shared inputs change.
Assert operation results, bounded
report attempts, causal category and privacy independently of logging callbacks.
Fix demonstrated producer/collector isolation defects, review resources, build
as required and retain runner evidence/cleanup. Close only 010a. Actual native
failure exports remain in 010b/010.
