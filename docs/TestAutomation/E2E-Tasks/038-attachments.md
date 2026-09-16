# 038 — Add, inspect, preview and remove attachments

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/attachments (154). Scope: FEED06, FEED07, FEED12, FEED13.

Required implemented capabilities: FILE03; FEED01, FEED03. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Extend FIX04 with bounded synthetic files. Implement add/list result, one item's name/size/order, optional offered preview, and removal with exact remaining list. No private storage reads; unoffered preview is explicitly inapplicable.

## Live VM acceptance

On the VM add multiple synthetic files, review the displayed list, preview only if offered, remove one and compare remaining entries. Exercise 5/6 files and 5 MiB/5 MiB+1 boundaries; aggregate size needs public diagnostic-size data or stays a local-test obligation.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
