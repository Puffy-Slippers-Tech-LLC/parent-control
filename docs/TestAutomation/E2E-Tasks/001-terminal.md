# 001 — Visible terminal launch, submission and denial

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-004/terminal (6). Scope: FILE01, FILE02, FILE06.

Required implemented capabilities: Existing qualified primitives and attempt envelope only. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Bind SEARCH05 to the normal terminal and UI21/UI03 to its nonsecret input/output. Implement FILE01, then separate FILE02 input from FILE06 result observation. Use the real Parent executable as the fixed standard-user command; command echo or a generic error cannot prove denial.

## Live VM acceptance

On the installed VM, sign in as the standard fixture, open Terminal, submit Parent once, read its specific management-denial message and prove the management window absent. Exercise an independently opened terminal entry and reject the wrong foreground surface. No administrator authentication is added.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_terminal`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
