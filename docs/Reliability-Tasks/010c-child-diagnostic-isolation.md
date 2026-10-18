# 010c — Child diagnostic failure isolation

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract child refresh/lock diagnostic isolation from 010a. Read the
[diagnostic contract](../SystemDesign/Logging-and-Feedback.md), complete child
refresh/lock producers, `sessionDiagnostics.js`, catalogue validators and their
canonical tests, including `tests/child/session_diagnostics.test.mjs`,
`session_unlock.test.mjs` and `resume_estimate_refresh.test.mjs`.
010a retains app process-exit/collector cleanup isolation; native exports remain
in 010b/010. No feedback submission is involved.

## Work sequence

1. Identify covered producer failures, including 004a's narrow authority guard;
   inject only a missing diagnostic writer or transport failure at successful
   refresh and lock/unlock boundaries. Reuse existing assertions without creating
   a second authority matrix.
2. Independently assert the original refresh/native-lock result and unchanged
   authority/deadline. Logging failure cannot throw into native callbacks, retry
   the underlying operation or leak child subscriptions/timers.
3. Check bounded reporting and retained operation/stage/category where collection
   remains available; report unavailable evidence accurately. Unrelated healthy
   events cannot clear the failed operation's incident. Use private exception,
   identity, path, remote-name and argument canaries with catalogue validation.
4. Run exact affected child-node/GJS and catalogue unit selections through
   `tools/run-tests`, with explicit timeouts; fix demonstrated child isolation
   defects and rerun affected branches.

## Acceptance and close-out

Retain independent operation results, report-attempt counts, sanitized evidence
and owned-callback cleanup. Review resource ownership and follow master build
rules. Close only 010c; host callbacks cannot establish native export survival.
