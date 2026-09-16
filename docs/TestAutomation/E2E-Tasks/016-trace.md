# 016 — Observe public transitions during input

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031 diagnostic collection (155), then E2E-005 saving. Scope: UI22.

Required implemented capabilities: UI16, FEED01/03 and the shared unique-stage/assertion support. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Extend the existing rendezvous with bounded trace readiness, one caller-owned input, and durable result collection. Use unique invocation/stage IDs and public state events. Retain failure latching and store-before-reply; do not create another runner or delay the product.

## Live VM acceptance

On installed feedback, start the observer before a normal public input and collect ordered control/validation samples through a declared final state. A missing required transient sample stays unproven. Pass the affected recorder/worker safety checks before the guarded live run.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
