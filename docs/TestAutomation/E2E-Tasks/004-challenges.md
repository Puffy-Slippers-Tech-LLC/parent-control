# 004 — Allow distinct single-use authentication challenges

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-002 (2), then all returning-user journeys. Scope: UI19/GDM05 challenge context; JourneyPlan repeated stages/assertions.

Required implemented capabilities: DESK02, DESK03, DESK04. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Replace the one-authentication-per-worker limitation with explicit challenge context for UI19/GDM05. Preserve two fresh recipient checks, wrong-recipient refusal, sealed captures, single use and terminal failure. Add unique repeated-stage IDs and per-assertion placement to JourneyPlan only as needed.

## Live VM acceptance

In one guarded VM attempt, authenticate the Parent, log out through the normal UI, then authenticate again with a new challenge. Reject stale/reused proofs in safety regressions; no reset of the existing failure latch. Run affected credential safety and ready cases 1, 3, 4, 5, 151.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_install`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
