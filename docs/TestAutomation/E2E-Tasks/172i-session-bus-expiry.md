# 172i — Check expiry after child bus replacement

Required tasks: 172c, 172e.
Estimate: 30–60 minutes.
Session exception: keep the finite fault/order, original deadline, recovery and
owned cleanup together on both supported targets.

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[system acceptance](../E2E-Execution-Contracts.md#system-acceptance), and
[expiry engineering contract](../UI-and-E2E-Coverage.md#expiry-engineering-contract).
Read only the affected current callbacks and shared mechanics, including their
callers, state and cleanup; discover actual selectors in area `session`.

## Scope and acceptance

Replace the actual child bus-daemon/broker process while expiry work is pending; pin process and bus-owner change. Observe protection through original expiry, retained work, peer input and bounded supported reconnection without stale recipient effects or awarded time. A client disconnect is insufficient. If bus replacement ends the desktop, record the retention mismatch; a new session cannot count as retained work. Live-bus lock-provider replacement belongs only to 172k.

This is installed system qualification, with no customer-case acceptance credit.
Extend the existing system-282 owner only for these missing assertions; reuse
covered mechanics and register the distinct binding once before execution.
Run the affected host checks with explicit timeouts and this installed delta on
`onpc-Ubuntu26.04` and `onpc-Fedora44`. Task completion does not rerun unchanged
predecessor checks or close any canonical customer row.

At [close-out](../E2E-Execution-Contracts.md#completion-and-document-cleanup),
record actual selectors, qualified scope and unresolved limits in the coverage
allocation and owning runtime documentation; advance only this queue row.
