# 001d — Child estimate-read retry budgets

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract the estimate-read retry engine from 001b. Read the
[screen-time contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
`child/timerQuery.js`, the `TimerUsage` adapter and necessary callers, then
`tests/child/timer_query.test.mjs` and the existing Gio classification checks.
This row owns `queryEstimatedTimes()` budgets and terminal outcomes; 001b owns
native query/replay cancellation and 001c owns controller lifecycle composition.
Preserve `9162f12d`'s registered Child/Parent Busy domains and nonretry identity
errors. Compare current tests before adding cases; construction by real Gio does
not prove that the daemon emits a chosen name. The 002 family owns native proof.

## Work sequence

1. Map existing coverage and add only missing Busy → owner loss → timeout/success
   and mixed terminal histories using fake clocks and explicit callbacks.
2. Assert shared attempt indices, the original 25-second total budget, bounded
   per-call timeouts and well-known-owner addressing on every retry. An overdue
   wake dispatches no new read; terminal failure releases the serialized queue.
3. Verify authorization, malformed replies and unknown Busy names stay terminal;
   a failed read cannot become zero usage. Check fixed categories with privacy
   canaries, using real Gio errors for any changed classifier.
4. Run exact affected child-node/GJS and adapter unit selections through
   `tools/run-tests`, with explicit timeouts; repair demonstrated defects and
   rerun affected histories.

## Acceptance and close-out

Retain dispatch counts/times, final categories, queue release and passing runner
evidence. Review changed resource ownership and follow master build/cleanup
rules. Close only 001d; host errors do not establish native service recovery.
