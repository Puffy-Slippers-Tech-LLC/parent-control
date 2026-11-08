# 172l — Check protection while locking is unavailable

Required tasks: 172j, 172k.
Estimate: 30–60 minutes.
Session exception: keep the finite fault/order, original deadline, recovery and
owned cleanup together on both supported targets.

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[system acceptance](../E2E-Execution-Contracts.md#system-acceptance), and
[expiry engineering contract](../UI-and-E2E-Coverage.md#expiry-engineering-contract).
Read only the affected current callbacks and shared mechanics, including their
callers, state and cleanup; discover actual selectors in area `session`.

## Scope and acceptance

Attempt a bounded identity-recorded lock-action outage leaving the original
Shell, session bus, unlocked desktop and ordinary applications alive. Confirm it
spans original exhaustion/revocation; observe actual input protection, retained
work and peer outcomes, then supported restoration of lock availability. A
request, restart, heartbeat or denied later login is insufficient. Do not
terminate ordinary work, relax policy or invent a fallback. Unsupported
protection remains expected-versus-actual with a return condition under Screen
time and the active brief; no skip/xfail or successful restoration supplies an
earlier protection pass. This characterization may close only after actual
attempts and owned cleanup on both targets; it grants no installed protection
acceptance or waiver of a production regression.

This is engineering characterization, with no passing protection or customer-case credit.
Extend the existing system-282 owner only for these missing assertions; reuse
covered mechanics and register the distinct binding once before execution.
Run the affected host checks with explicit timeouts and this installed delta on
`onpc-Ubuntu26.04` and `onpc-Fedora44`. Task completion does not rerun unchanged
predecessor checks or close any canonical customer row.

At [close-out](../E2E-Execution-Contracts.md#completion-and-document-cleanup),
record actual selectors, qualified scope and unresolved limits in the coverage
allocation and owning runtime documentation; advance only this queue row.
