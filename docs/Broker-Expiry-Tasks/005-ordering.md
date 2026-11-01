# 005 — Reject outdated expiry work

Acceptance: host

Required tasks: 002.
Estimate: 20–30 minutes.

Read the [master](../Broker-Expiry-Plan.md), Broker/State ownership and complete
current authority/transaction callbacks. Extend existing `test_core` ordering
and `test_private_dbus_service` dispatch checks. No scheduler or effect owner is
implemented by this task; unsupported future effects remain explicitly pending.

Use controlled orderings at existing broker time-query/management callbacks:
authoritative renewal, live revoke, allowance change and control disablement
versus an in-flight remaining-time read. Assert committed order, Busy/refusal,
rollback and existing caller/session authorization independently; not every
concurrent operation succeeds. Positive daily time remains usable after grant
removal. Extend only assertions missing from the current core/dispatch owners.

Establish each interleaving with existing controlled callbacks/events and a
bounded join. Do not use small sleeps, thread speed or repeated runs to obtain
the desired order; assert the actual commit/refusal order independently of
which worker finishes first.

Reuse existing retry/cancellation and identity regressions rather than repeating
the reliability 001 family or E2E residual matrices. Test meaningful existing
broker state/dispatch contracts, not a mock of an invented future scheduler.
Future queued lock effects must revalidate current entitlement, child/session
and reused account identity. They are external replacement acceptance gates in
the master, not prerequisites for completing this current-code TA slice.

Run the smallest affected unit/component selections with explicit timeouts;
discover actual filenames/selectors first. No installed pass is claimed.
