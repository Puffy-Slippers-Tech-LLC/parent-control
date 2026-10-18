# 001c — Resume lifecycle cancellation

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: 001a, 001b.
Estimate: 15–30 minutes.

## Deliverable and route

Extract controller lifecycle cancellation from 001. 001a supplies broker-query
budgets; 001b supplies child-query budgets and query-level cancellation. Read the
[screen-time lifecycle](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
the complete `resumeEstimateRefresh.js` controller, its `TimerUsage` adapter,
lifecycle callers and `tests/child/resume_estimate_refresh.test.mjs`.
Reuse existing fake clocks and explicit callbacks rather than sleeps.

## Work sequence

1. Identify existing coverage for inactivity, resume, disable and close while
   a query or replay is pending. Add only missing controller compositions.
2. Cancel immediately before dispatch and deliver a reply after cancellation.
   Observe no prohibited native call, result publication or scheduled retry.
3. Check preserved prior estimates and identical replay endpoints. Continuous
   activity cannot trigger extra usage replay or extend the original deadline.
4. Run exact affected child-node/GJS and adapter unit selections through
   `tools/run-tests`, with explicit timeouts; fix demonstrated lifecycle defects
   and rerun the affected compositions.

Retain passing runner evidence and owned-callback cleanup, review changed host
resources and follow master build rules. Close only 001c. Operation-specific
incident rearming and no-deadline/finite-deadline/refusal recovery remain in 001;
host callbacks do not qualify installed service recovery.
