# 079 — Choose app access and compose policy editing

Budget: 40–60 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-005/006 and E2E-019. Scope: PARENT16, FLOW03 and native APP02/FLOW08 policy-result bindings.

Required implemented capabilities: PARENT13, PARENT15; PARENT12, PARENT10, PARENT11; PARENT09, FLOW02; native grid/command fixtures, FILE05 and retained app visits. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement access-choice UI15 binding, saving and row readback; then compose FLOW03 search, optional filters, match draft/save and access choice. Qualify precise/pattern fixture data, native grid/command denial and APP02's previously observed window-closure result. Extend FLOW08's denied branch only after those observations; it must never send APP03 input to a denied app. Desktop/file-manager bindings remain with their own route capability.

## Live VM acceptance

On the VM, set Allowed, Hard blocked and Soft blocked through Parent, observe saved rows and launch matching/nonmatching prepared native targets through normal child UI. Before each policy transition that requires closure, open the target permissively and capture its window. After the block, independently observe that window's closure and prove the declared fresh usable or named denial result through FLOW08. Screen-time disablement does not erase app rules.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_app_routes`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
