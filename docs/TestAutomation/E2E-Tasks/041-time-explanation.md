# 041 — Read remaining time and configure time controls

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-005 (7–12). Scope: PARENT09, FLOW02.

Required implemented capabilities: PARENT05, PARENT06; PARENT08. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement PARENT09's non-collapsing expanded explanation first. Compose FLOW02 with conditional enable, allowance commit/save, explicit final enablement, settings and explanation. Disabling clears a grant and is never navigation.

## Live VM acceptance

On the VM, configure positive then zero daily allowance and read daily/one-time/total explanations. Repeated PARENT09 reads leave the section expanded. Compare displayed values with rounding bounds and observe real saves.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_allowance`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
