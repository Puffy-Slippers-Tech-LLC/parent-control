# 001b — Child timer-query cancellation

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: 001d.
Estimate: 15–30 minutes.

## Session boundary

Deliver native query/replay cancellation and late-reply suppression. 001d
supplies estimate-read budgets and error classification; this row's cumulative
scope retains them without reimplementing the retry engine. Controller lifecycle
composition remains in 001c and operation-specific incidents remain in 001.

## Deliverable and route

Complete the child timer client's remaining cancellation slice of original 001.
Read `child/timerQuery.js`, its `TimerUsage` adapter and necessary callers under
[screen-time enforcement](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement).
Extend `tests/child/timer_query.test.mjs` and existing classification adapters,
using fake clocks and explicit callbacks instead of sleeps.

## Work sequence

1. Map actual cancellation handles and owner guards at queued query/replay
   boundaries. Do not assume every estimate-read API accepts native cancellation.
2. Cancel a queued usage query immediately before dispatch and assert no native
   call. Cancel an in-flight query before replay selection/write; a late reply
   cannot dispatch a successor write, publish a result or schedule another read.
3. Deliver a late completion after an already-dispatched replay write. Preserve
   its actual outcome without claiming the write was unsent; prevent successor
   work and release owned queue/callback state. Preserve exact self-read replay
   endpoints and prior verified estimates; no fabricated or empty usage record.
4. Reuse 001d's budgets/categories, rerunning affected branches if cancellation
   changes their inputs. Keep original attempt indices, deadlines, terminal
   categories and privacy canaries.

## Acceptance and close-out

Run exact affected child-node/GJS and adapter unit files through
`tools/run-tests`, preserving explicit timeouts. Assert dispatch counts, bounded
timing, cancellation and observable result callbacks. Fix demonstrated client
defects, retain runner evidence, review resource changes, and follow master
build/cleanup rules. Close only 001b; fake D-Bus outcomes do not qualify native
owner loss.
