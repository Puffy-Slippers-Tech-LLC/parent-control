# 006 — Perform a customer package operation

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-002 (2). Scope: LIFE04.

Required implemented capabilities: product-free journey entry with verified assets; FILE01/02/06 and qualified AUTH03/UI19. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose FILE01/02/06, the optional AUTH03 twice → UI19 → submit branch, then FILE06 completion. Begin with install, verified asset path and final notice; extend update/remove/reinstall/purge profiles only with their consumers.

## Live VM acceptance

From a product-free guarded VM attempt, install the verified package through the visible administrator terminal and real authentication, then read successful completion and final reboot-required text. Color is not an acceptance condition.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_install`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
