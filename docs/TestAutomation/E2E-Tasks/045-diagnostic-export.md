# 045 — Save and open customer-selected diagnostics

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/diagnostic-export (155). Scope: FEED08.

Required implemented capabilities: FILE03's save branch, FILE04/07, FEED01/03, FEED09's collection trace and DESK10 on the Parent desktop. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Compose the real Download, Save chooser, file-manager navigation and actual viewer. Register bounded expected public export headings and the viewer/feedback DESK10 bindings, without opening source product logs or collector internals.

## Live VM acceptance

On the VM observe diagnostic collection, save output to the selected directory, open it through the file manager and read the expected public headings. Return to the still-open feedback dialog without editing its draft.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
