# 008a — Request readiness and locale retry

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: 008c.
Estimate: 15–30 minutes.

## Session boundary

Deliver RequestWindow's current-request readiness and submission composition.
008c supplies locale-job failure/retry, warm-up queue ordering, supersession and
late-job cleanup. Together these preserve this row's original obligations and
the agent-preparation failure slice from 009; do not repeat the manager matrix.

## Deliverable and route

Read the [frontend lifecycle](../SystemDesign/Frontends.md), `main.py:RequestWindow`'s
preference-save, agent-prepared, failure and close callbacks, their callers and
complete canonical host tests in `tests/unit/test_request_time_estimate.py`.
Compose the real locale manager's maintained interface from 008c using explicit
job callbacks and fake deadlines; native timing is not the race oracle.
The retained guards bind one frontend request revision and stage, not a visit
token or private confinement receipt. Machine preparation deadlines do not bound
human time in a genuine parent-authentication prompt.

## Work sequence

1. Begin one current request while speculative preparation is pending. Preference
   persistence and required current-language preparation must complete before
   RequestAccess; grant/approval dispatch count remains zero until then.
2. Fail preparation, observe refusal without submission, then perform the
   supported retry. Exactly one current request may submit after success;
   stale language or a completed restart for another request cannot authorize it.
3. Supersede the request/recipient/language or close the window before completion,
   then deliver a late preparation callback. Assert no stale/duplicate submission,
   preserved recipient checks and released current-request resources.
4. Run exact affected host unit/UI selections through `tools/run-tests`, with
   explicit timeouts, fixing demonstrated composition defects. Reuse 008c's
   direct manager tests and rerun only branches affected by changed inputs.

Preserve durability and original deadlines. Reuse already-covered branches;
add only missing compositions.

## Acceptance and close-out

Run exact affected host unit/UI selections through `tools/run-tests`, with
explicit timeouts and resource classification appropriate to each owner. Assert
job/submission counts, refusal before readiness, correct later authorization and
closed-owner cleanup. Fix demonstrated lifecycle defects, retain runner evidence
and follow master build/cleanup rules. Close only 008a. It supplies neither a
native pending-warm-up witness nor the three installed functional cycles in 008.
