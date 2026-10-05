# 050 — Confirm grant revocation and read balances

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add Confirm and independent saved time readback. Reuse 050a's warning/target and Cancel; child effects remain later consumers.

Reuse the delivered scope of tasks **050a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **PARENT17, PARENT18**. First scheduled consumer: [E2E-008, case 22](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **050a** — PARENT17/18 revocation target, warning and Cancel.

## Implementation

Implement the warning/target observation and explicit Cancel/Confirm, then independently verify saved time and settings. Warning dismissal is shared navigation, not a separate acceptance result. Obtain the grant through kiosk approval.

## Live VM acceptance

On the VM with a real grant, Cancel preserves displayed settings/balance within elapsed-time bounds. Reopen, Confirm, and independently read the new daily/one-time explanation. Child effects remain separate later observations.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_revocation
```
