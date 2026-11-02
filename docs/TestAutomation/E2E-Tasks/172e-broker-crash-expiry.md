# 172e — Check expiry across a broker crash

Required tasks: 172c.
Estimate: 30–60 minutes.
Session exception: keep the finite fault/order, original deadline, recovery and
owned cleanup together on both supported targets.

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[system acceptance](../E2E-Execution-Contracts.md#system-acceptance), and
[expiry engineering contract](../UI-and-E2E-Coverage.md#expiry-engineering-contract).
Read only the affected current callbacks and shared mechanics, including their
callers, state and cleanup; discover actual selectors in area `session`.

## Scope and acceptance

Crash the exact identity-recorded broker during usable child activity, including a pending lock-request boundary. Confirm the fault before original expiry and observe input protection through the outage, retained work and unaffected peer. Supported recovery must reconstruct current native balance, grant and session within the outage-inclusive budget, without duplicated time, replayed approval or stale effects. Service liveness alone is insufficient; missing restart behavior is a boundary to report, not authority to install supervision.

This is installed system qualification, with no customer-case acceptance credit.
Extend the existing system-282 owner only for these missing assertions; reuse
covered mechanics and register the distinct binding once before execution.
Run the affected host checks with explicit timeouts and this installed delta on
`onpc-Ubuntu26.04` and `onpc-Fedora44`. Task completion does not rerun unchanged
predecessor checks or close any canonical customer row.

At [close-out](../E2E-Execution-Contracts.md#completion-and-document-cleanup),
record actual selectors, qualified scope and unresolved limits in the coverage
allocation and owning runtime documentation; advance only this queue row.
