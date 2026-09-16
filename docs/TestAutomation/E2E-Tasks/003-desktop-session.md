# 003 — Open session controls and switch or sign out

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-002 (2) and retained-user consumers. Scope: DESK02, DESK03, DESK04.

Required implemented capabilities: Existing qualified primitives and attempt envelope only. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement the session menu first; then normal Switch User and normal Logout with explicit confirmation. Extend DESK01/GDM07 routing to named child/other-parent fixtures only when used. Route metadata never supplies customer assertions.

## Live VM acceptance

In separate live VM attempts, enter an observed Parent desktop, open its session menu and perform Switch User or Logout with the declared confirmation. Observe GDM after each; leave the existing desktop retained after Switch User; this slice observes GDM only. Window retention is verified after the retained-unlock capability is qualified. Never infer a second same-child session from account selection.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_install`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
