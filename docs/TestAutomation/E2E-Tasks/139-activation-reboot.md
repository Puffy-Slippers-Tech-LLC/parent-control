# 139 — Follow reboot activation after a real update

Budget: 30–50 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-026/reboot (138). Scope: LIFE04's matching update profile and LIFE05's reboot activation route.

Required implemented capabilities: LIFE02, LIFE04(update foundation), GDM07, FLOW15/FLOW01 retained entry, FLOW03 and overlay choices/exits. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Bind a verified old/new package profile requiring reboot activation. Extend LIFE04(update) and LIFE05 only for this route. Follow the displayed requirement for every named affected app/user; preserve all mechanical migration obligations.

## Live VM acceptance

On the VM install the real update, read its reboot requirement, perform the normal reboot/login sequence and read settings before edits. Run the affected existing package activation checks separately.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_activation`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
