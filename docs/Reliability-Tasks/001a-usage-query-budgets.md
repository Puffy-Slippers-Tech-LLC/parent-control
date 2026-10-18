# 001a — Broker usage-query retry budgets

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Complete only the missing helper retry/error histories from original task 001.
Read the complete usage-query helper, its broker adapter and callers through the
[screen-time design](../SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities),
then `tests/unit/test_usage_query_retry.py` and `test_adapters.py`.
Retain the existing `5b15f17d` assertions and fake monotonic clock adapters.

Exercise Busy → owner loss → timeout/success and mixed terminal failures.
All failures share original attempt indices and the 25-second total budget;
per-call deadlines stay bounded. A delayed wake after budget expiry dispatches
no new call. Authorization, malformed replies and unknown Busy names remain
terminal; a failed read never becomes zero usage. Check adapter exit/status
mapping retains the reviewed terminal category without raw exception,
remote-name, argument or identity canaries. Use real Gio classification for any
changed classifier, rather than proving only a fake error's shape.

## Acceptance and close-out

Run exact affected unit files through `tools/run-tests unit`, with explicit
timeouts; include affected GJS checks if classification changes. Assert attempt
counts, dispatch times, unchanged budget and final category. Fix demonstrated
helper/adapter defects and review changed resource ownership. Follow master
build, cleanup and evidence rules; record actual passing selections and close
only 001a. Child cancellation and resume incidents remain in 001b/001; native
service recovery remains in 002a/002.
