# 172c — Apply the latest time decision at expiry

Required tasks: 172a.
Estimate: 30–60 minutes.
Session exception: keep the finite fault/order, original deadline, recovery and
owned cleanup together on both supported targets.

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[system acceptance](../E2E-Execution-Contracts.md#system-acceptance), and
[expiry engineering contract](../UI-and-E2E-Coverage.md#expiry-engineering-contract).
Read only the affected current callbacks and shared mechanics, including their
callers, state and cleanup; discover actual selectors in area `session`.

## Scope and acceptance

Extend only missing core/dispatch order assertions with controlled events and bounded joins: renewal, revoke, allowance change and disablement versus an in-flight time read/current expiry callback. Assert actual commit, Busy/refusal and rollback order, not universal success. Reuse obligation 148’s existing conflict/dispatch coverage. Installed histories observe usable entitled desktops, bounded locking when restricted, retained work and peer continuity. Ready both actors before the boundary; sleeps and repeated races cannot establish ordering. No invented scheduler or future effect owner is tested.

This is installed system qualification, with no customer-case acceptance credit.
Extend the existing system-282 owner only for these missing assertions; reuse
covered mechanics and register the distinct binding once before execution.
Run the affected host checks with explicit timeouts and this installed delta on
`onpc-Ubuntu26.04` and `onpc-Fedora44`. Task completion does not rerun unchanged
predecessor checks or close any canonical customer row.

At [close-out](../E2E-Execution-Contracts.md#completion-and-document-cleanup),
record actual selectors, qualified scope and unresolved limits in the coverage
allocation and owning runtime documentation; advance only this queue row.
