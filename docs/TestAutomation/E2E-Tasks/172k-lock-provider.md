# 172k — Check locking after a temporary interruption

Required tasks: 172c, 172j.
Estimate: 30–60 minutes.
Session exception: keep the finite fault/order, original deadline, recovery and
owned cleanup together on both supported targets.

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[system acceptance](../E2E-Execution-Contracts.md#system-acceptance), and
[expiry engineering contract](../UI-and-E2E-Coverage.md#expiry-engineering-contract).
Read only the affected current callbacks and shared mechanics, including their
callers, state and cleanup; discover actual selectors in area `session`.

## Scope and acceptance

Exercise a temporarily unavailable native lock action within the original live
desktop. Observe actual protected input, retained work, peer continuity and
bounded supported recovery. Confirm availability and legitimate renewal commit
directly; entitled state must prevent a stale retry. Reuse 172j's observations
without repeating its acknowledgement matrix. Missing retry behavior remains
explicit.

The required protection and renewal results are settled acceptance. Recovery of
lock availability alone cannot pass a history whose required protection or retry
was absent. Keep that implementation gap incomplete under the shared failure
contract; do not reinterpret this task as the characterization-only scope owned
by 172l.

Implement missing transient-failure recovery within the existing owned
enforcement callback/timer. Keep one public `Lock` call in flight, bound each
call and the finite retry sequence by the existing absolute timed-lock window,
and revalidate the current session, verified entitlement and original deadline
before dispatch. Secure lock, legitimate renewal, disablement, owner
invalidation and disposal cancel stale retry authority. A later current
confirmed exhaustion may establish its own enforcement decision. Retry spacing
and count are implementation choices within that unchanged bound. Introduce no
separate expiry scheduler, fallback lock, service supervisor, logout or
termination of ordinary work. This is bounded repair of the existing
[repeated-enforcement behavior](../../Specification.md#screen-time-setup-and-enforcement),
not a new protection policy for persistent lock unavailability.

This is installed system qualification, with no customer-case acceptance credit.
Extend the existing system-282 owner only for these missing assertions; reuse
covered mechanics and register the distinct binding once before execution.
Run the affected host checks with explicit timeouts and this installed delta on
`onpc-Ubuntu26.04` and `onpc-Fedora44`. Task completion does not rerun unchanged
predecessor checks or close any canonical customer row.

At [close-out](../E2E-Execution-Contracts.md#completion-and-document-cleanup),
record actual selectors, qualified scope and unresolved limits in the coverage
allocation and owning runtime documentation; advance only this queue row.
