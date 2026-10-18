# 001b — Child timer-query cancellation

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Complete the child timer client's retry/cancellation slice of original task 001.
Read `child/timerQuery.js`, its `TimerUsage` adapter and necessary callers under
[screen-time enforcement](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement).
Extend `tests/child/timer_query.test.mjs` and existing classification adapters,
using fake clocks and explicit callbacks instead of sleeps.

Cover Busy → owner loss → timeout/success and mixed terminal outcomes sharing
the original attempt index and total budget. Check overdue wake dispatches no
new call, each retry resolves the well-known owner, cancellation immediately
before dispatch prevents it, and replies after cancellation cannot publish a
result or schedule another read. Preserve prior verified estimates and exact
Busy allowlists; authorization and unknown errors stay terminal. Assert the
original terminal category with privacy canaries and use real Gio errors for
changed classification. Lifecycle/replay and operation-specific incidents
remain in 001.

## Acceptance and close-out

Run exact affected child-node/GJS and adapter unit files through
`tools/run-tests`, preserving explicit timeouts. Assert dispatch counts, bounded
timing, cancellation and observable result callbacks. Fix demonstrated client
defects, retain runner evidence, review resource changes, and follow master
build/cleanup rules. Close only 001b; fake D-Bus outcomes do not qualify native
owner loss.
