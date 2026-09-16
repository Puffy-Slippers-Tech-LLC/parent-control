# 029 — Open feedback and read synthetic drafts

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/validation (153). Scope: FEED01, FEED03.

Required implemented capabilities: Existing qualified primitives and attempt envelope only. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Register feedback editor, body/reply, attachments, validation and collection snapshots. Implement FEED01 entry and FEED03 immutable bounded synthetic observations. Keep Send untouched.

## Live VM acceptance

In installed Parent, open feedback and observe editor readiness, initial draft, exact attachment set and control states. Repeat FEED03 from an independently opened dialog; private drafts and arbitrary text projections remain unavailable.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
