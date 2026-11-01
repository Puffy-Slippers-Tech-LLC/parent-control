# 012 — State the limits of unavailable secure locking

Acceptance: review

Required tasks: 011, 011a.
Estimate: 30–60 minutes; real outage and restoration remain indivisible.

Read the [master](../Broker-Expiry-Plan.md) and design's unavailable secure-lock
boundary. Extend the same installed owner with planned parameter `secure-lock-outage`
(unimplemented). Use a bounded identity-recorded Shell/lock-service outage that
leaves an already unlocked desktop, not only a disconnected test client.

Observe input protection through original exhaustion/revocation and exact
retained-work/peer outcomes, then supported restoration. A sent request, restart,
watchdog heartbeat or denied future login cannot supply the missing protection.
Neither extension nor broker can independently repair a hung compositor lock.
Do not terminate the session, close ordinary work, relax policy or invent an
undocumented fallback to turn this condition into success.

Confirm the outage spans the required exhaustion/revoke event; a late fault or
observer is an invalid history, not evidence of protection. A successful
restoration read cannot establish timely locking during the earlier outage.

If protection cannot be achieved while preserving work, retain that unsupported
boundary in the design and final handover blocker, with expected versus actual
behavior and return condition. A demonstrated unsupported limit is not a passing
handover history; handover stays blocked until an explicit behavior decision
resolves the claim. No skip/xfail may satisfy the protection gate. This review
row may complete only the bounded characterization and truthful limitations;
it grants no installed protection acceptance and cannot waive a current-path
product regression, which still follows failure handling.

Run the supported fault/restoration attempt on `onpc-Ubuntu26.04` and
`onpc-Fedora44` with owned cleanup; both actual attempts are required despite
this row's review metadata. Missing fault ownership/readiness blocks the row;
stop safely if the maintained route cannot own/recover the affected process.
