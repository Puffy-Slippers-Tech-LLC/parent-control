# 050 — Cancel and confirm grant revocation

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-007/single (17, 19). Scope: PARENT17, PARENT18.

Required implemented capabilities: PARENT08; PARENT09, FLOW02; FLOW05, FLOW06, FLOW07; DESK09/10; FLOW15 and FLOW01 retained scopes. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement the warning/target observation, then explicit Cancel/Confirm, closure, saved-state and settings observations. A grant is obtained through kiosk approval; no grant state is seeded internally.

## Live VM acceptance

On the VM with a real grant, Cancel preserves displayed settings/balance within elapsed-time bounds. Reopen, Confirm, and independently read the new daily/one-time explanation. Child effects remain separate later observations.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_revocation`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
