# 008a — Request readiness and locale retry

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Own the deterministic warm-up/Request ordering from 008 and agent-preparation
failure/retry ordering from 009. Read the
[frontend lifecycle](../SystemDesign/Frontends.md), agent-locale preparation,
Request callbacks and complete canonical request/agent host tests, including
relevant `test_request_time_estimate.py` coverage. Use explicit job callbacks and
fake deadlines; native timing is not the race oracle.

Request during pending speculative locale warm-up must await the required
preparation for the current recipient/language. Cover failed speculative warm-up,
required retry, superseding language, close and late replies. A completed restart
for the wrong request never authorizes submission. Successful required retry
permits only the current request, with no duplicate job/submission or leaked
preparation timer. Preserve recipient checks, durability and original deadlines.
Reuse already-covered branches; add only missing compositions.

## Acceptance and close-out

Run exact affected host unit/UI selections through `tools/run-tests`, with
explicit timeouts and resource classification appropriate to each owner. Assert
job/submission counts, refusal before readiness, correct later authorization and
closed-owner cleanup. Fix demonstrated lifecycle defects, retain runner evidence
and follow master build/cleanup rules. Close only 008a. It supplies neither a
native pending-warm-up witness nor the installed timing samples required by 008.
