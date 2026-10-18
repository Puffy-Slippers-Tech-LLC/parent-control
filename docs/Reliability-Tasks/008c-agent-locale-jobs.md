# 008c — Agent-locale job failure and ordering

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract the locale manager's asynchronous job contract from 008a. Read the
[frontend lifecycle](../SystemDesign/Frontends.md), the complete
`kiosk/oh_no_parent_control_kiosk/agent_locale.py`, its callers and agent tests in
`tests/unit/test_request_time_estimate.py`. Reuse explicit bus/job callbacks,
private runtime files and fake deadlines; no real service restart is needed.
008a owns the separate RequestWindow submission composition.

## Work sequence

1. Map existing tests for `KioskAgentLocale`; add only missing environment-write,
   restart-reply, job-result and timeout failure/retry orderings. Failure must
   invalidate previously applied settings rather than reuse a stale locale.
2. Deliver matching JobRemoved before and after the restart reply, plus unrelated
   job results. Only completion of the matching job may satisfy its callback.
3. Queue required preparation during speculative warm-up, then supersede the
   speculative language. Required callbacks retain order; successful matching
   work may be reused, and failed warm-up requires a real successful retry.
4. Close or expire a pending operation, then deliver late replies. Assert bounded
   job/callback counts, inert stale revisions and released subscriptions/timers.
   Run the exact affected unit selections through `tools/run-tests`, with
   explicit timeouts, repairing demonstrated manager defects.

## Acceptance and close-out

Assert callback errors/success, applied environment and owned cleanup independently
of logs. Preserve recipient-independent locale mechanics and privacy canaries;
do not add a new queue or preparation path. Follow master build/resource/evidence
rules and close only 008c. Request authorization still requires 008a; installed
startup/exit under enlarged inventory still requires 008's three functional cycles.
