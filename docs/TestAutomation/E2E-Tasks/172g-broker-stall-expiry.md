# 172g — Check expiry while the broker stalls

Required tasks: 172e.
Estimate: 30–60 minutes.
Session exception: keep the finite fault/order, original deadline, recovery and
owned cleanup together on both supported targets.

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[system acceptance](../E2E-Execution-Contracts.md#system-acceptance), and
[expiry engineering contract](../UI-and-E2E-Coverage.md#expiry-engineering-contract).
Read only the affected current callbacks and shared mechanics, including their
callers, state and cleanup; discover actual selectors in area `session`.

## Scope and acceptance

Hold one bounded real identity-recorded broker process stall across original expiry; a slow mock reply is insufficient. Observe secure input protection, retained work and peer continuity, then resume only the same owned process. Require reconstruction within the outage-inclusive budget without stale locks, duplicate time or approval replay. Reuse crash recovery mechanics; useful deadline progress is distinct from process liveness.

This is installed system qualification, with no customer-case acceptance credit.
Extend the existing system-282 owner only for these missing assertions; reuse
covered mechanics and register the distinct binding once before execution.
Run the affected host checks with explicit timeouts and this installed delta on
`onpc-Ubuntu26.04` and `onpc-Fedora44`. Task completion does not rerun unchanged
predecessor checks or close any canonical customer row.

At [close-out](../E2E-Execution-Contracts.md#completion-and-document-cleanup),
record actual selectors, qualified scope and unresolved limits in the coverage
allocation and owning runtime documentation; advance only this queue row.
