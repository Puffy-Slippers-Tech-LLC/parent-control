# 152 — Change connectivity through public network controls

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-033/retry (157). Scope: LIFE06.

Required implemented capabilities: FEED11/14, DESK02, UI17 and DESK10's feedback binding; authorization must cover the retry submission. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

Prerequisite gate: **Supported customer connectivity route preserving safe observation**. If unavailable, leave this task unchecked with the concrete blocker/return condition in the master; continue independent work. An applicability check alone does not complete it.

## Work

Qualify the supported normal network UI, displayed connectivity and FEED09's actual retry-state projection. Bind disconnect/reconnect and restoration deadline within the actual retry window; preserve VM observation/ownership transport. Do not inject transport faults or forge responses.

## Live VM acceptance

In the authorized live retry attempt, disconnect through UI, submit once, observe retry, reconnect before its deadline and observe automatic success for that same submission. If network controls also sever required harness access with no supported route, retain the blocker.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_retry`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
