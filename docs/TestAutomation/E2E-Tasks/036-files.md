# 036 — Navigate the file manager and copy or rename fixtures

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031 attachments/export (154, 155). Scope: FILE07, FILE04 and FILE05 with finite synthetic files.

Required implemented capabilities: UI16 and the existing SEARCH05 launch adapter; bind its normal file-manager window here. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Stage a small fixed set of harmless synthetic files through FIX04 for this consumer, including paths with spaces. Implement Location navigation first, file-manager entry observation next, then copy/rename with exact selection and resulting entries. Native executable and AppImage routes are a separate extension.

## Live VM acceptance

On the VM open the normal file manager, navigate to the synthetic directory, select the exact file, copy and rename through normal UI, and observe the expected entries independently. Supply an independently opened file manager as another entry; wrong/absent destinations refuse without fallback.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
