# 190k — Stop a report at the request station

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the direct Stop sending and close action and independently observe GDM.
Reuse 190b's retry-entry/readback operations. Stopping cannot recall an already
accepted request; restore connectivity after exit.

Reuse the delivered scope of tasks **190b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **FEED09 retry and FEED17/18 kiosk**. First scheduled consumer: [E2E-047, case 219](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **190b** — FEED09 kiosk retry/reconnection and FEED17 pending Stop action; gate in brief.

## Implementation

Reuse 190b's authorized retry-entry and FEED17 read operations, then activate
FEED18 Stop sending and close once with its exact GDM destination. The action
stops directly; no warning dialog, confirmation response or stay choice is part
of the product contract. Do not infer recall of remote delivery.

## Live VM acceptance

In a fresh guarded VM attempt with an authorized synthetic report reached
through its public error, use LIFE06 to remove Internet access, Send once and
observe retry. Read the owned Stop action, activate it once and independently
require report disappearance and GDM. Preserve shared wrong-surface/owner and
uncertain-input refusals without replaying Send. Restore Internet access through
the same LIFE06 helper from GDM; no Parent login is needed. Reuse 190b's unchanged
retry-entry binding; its evidence supplies no saved VM state. Case 219 owns the
complete journey.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_stop_a_sending_kiosk_report
```
