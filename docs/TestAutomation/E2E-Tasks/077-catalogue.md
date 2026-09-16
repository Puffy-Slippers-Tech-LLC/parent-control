# 077 — Read and filter the public app catalogue

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-006; E2E-019. Scope: PARENT12, PARENT10, PARENT11.

Required implemented capabilities: UI16; UI17; APP01/02/03 native grid/command scope. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement row observation, then public search with exact bounded result sets, then both access/match filter popovers using UI17. Empty expected results are explicit; search reads no installed catalogue backend.

## Live VM acceptance

On installed Parent, search the prepared native app and an absent name, then change each filter's declared option set. Observe exact rows including zero and read the named app's current access/match settings.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_catalogue`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
