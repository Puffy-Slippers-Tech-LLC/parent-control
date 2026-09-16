# 116 — Qualify supported Flatpak launch routes

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-019/Flatpak (98–109). Scope: FIX04 and APP01/02/03 Flatpak scope.

Required implemented capabilities: PARENT16, FLOW03; APP04, FLOW08, FLOW09, FLOW14. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Extend FIX04 through supported preparation for one real pinned Flatpak fixture. Bind grid and command APP01/02/03/SEARCH selectors and public effects; keep route data distinct from Snap.

## Live VM acceptance

On the VM launch/use the real Flatpak through both routes, then apply a Parent block and observe the proper hidden/denied result. Missing package/support blocks the route; no native substitute.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_app_routes`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
