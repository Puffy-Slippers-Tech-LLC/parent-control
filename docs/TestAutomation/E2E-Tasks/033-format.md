# 033 — Apply and observe rich-text formatting

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/draft-reopen (152). Scope: UI24, FEED04.

Required implemented capabilities: UI16; FEED01, FEED03. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Read public accessibility formatting attributes for an explicit synthetic range (UI24), then compose normal keyboard selection and toolbar/menu input (FEED04). Unavailable public attributes are a blocker, not permission for a DOM bridge.

## Live VM acceptance

In installed feedback, format one synthetic range and independently read its public attributes; an adjacent unformatted range must differ. A pressed toolbar control alone does not pass.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
