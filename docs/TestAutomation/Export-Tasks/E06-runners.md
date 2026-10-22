# E06 — Capture runner results at terminal boundaries

Acceptance: host
Requires: E05a

## Purpose and delivery

Integrate the shared handoff into every runner producer assigned by E01, under
the [master](../Export-Execution-Plan.md) and
[capture contract](../Export-Design.md#capture-and-publication). Read complete
`regression.Report`, `Execution`, terminal category/aggregate closure and worker
handoffs, `regression_events.py`, `test_commands.py` and their shared report
consumers. E06a owns qualification and E2E collector integrations.

Emit structured exact check/selection/target/attempt records and capture finalized
result dependencies before another run can rotate them. Attach cleanup when its
owner finishes; incomplete cleanup never becomes passing proof. Preserve failed
and interrupted attempts, worker versus batch provenance and original inventories.
Do not change selectors, scheduling, test outcomes, fixture preparation, VM
ownership or the latest-only watch recording policy. Include standalone and
first-use report routes, not only the aggregate happy path. Split independent frozen
producer families before this row if needed; no unassigned producer is complete.

## Validation and close-out

Use synthetic runner/helper fixtures to exercise terminal success,
assertion failure, setup/teardown failure, interruption, two targets, aggregate
join and source rotation. Check exact selected IDs and retained result/input/log/
cleanup dependencies. Test helper denial without authentication retry. Run
the [older-report rotation history](../Export-Design.md#required-regression-histories):
create report A and its declared consumer/reference, then start later runner
sessions through startup retention until A's original path is actually retired.
Resolve the exact check/attempt/target/inputs and complete command/cleanup closure
through the stable record without a check rerun. Include more than three runs;
assert A's original path is absent, its invocation count remains one and every
required record matches the saved original bytes/digests after resolution.
E04's failed-capture control must preserve the original before acknowledgement.
Extend existing runner/evidence/storage modules; review resource-affecting changes
under host parallelism. Run scoped maintained host tests with explicit timeouts, update
delivered report/evidence contracts and follow the master's owned close-out.
