# 050 — Confirm grant revocation and read balances

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
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

- **050a** — PARENT17/18 revocation target, warning and Cancel.

## Implementation

Reuse 050a's warning/target operation and add explicit Confirm, then independently verify saved time and settings. Warning dismissal is shared navigation, not a separate acceptance result. Obtain the grant through kiosk approval.

## Live VM acceptance

In a fresh guarded VM attempt with a real kiosk-approved grant, open the owned warning, verify its child target, Confirm once and independently read the new daily/one-time explanation and saved settings. Qualify independent valid entry and wrong-child/confirmation refusal. Reuse 050a's unchanged exact warning/Cancel qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state. Child effects remain separate later observations.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_revocation
```
