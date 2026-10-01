# 190k — Stop a sending kiosk report

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add Stop sending and close, independently observing GDM. Reuse 190b's retry/warning/stay branch. Preserve the warning that stopping cannot recall an already accepted request and restore connectivity.

Reuse the delivered scope of tasks **190b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **FEED09 retry and FEED17/18 kiosk**. First scheduled consumer: [E2E-047, case 219](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150k** — FEED11, FEED09 success and FEED14 kiosk; gate in brief.
- **152** — FEED09 Parent retry/recovery over qualified LIFE06; gate in brief.
- **190b** — FEED09 retry and FEED17/18 kiosk stay-open branch; gate in brief.

## Implementation

Bind retry on the kiosk report after LIFE06 removes the VM's Internet access, then implement FEED17 before FEED18. Declare stay-open and Stop sending and close responses and their exact destinations; stopping cannot recall an already accepted request.

## Live VM acceptance

On the VM with an authorized synthetic report, use LIFE06 to remove Internet access, Send once and observe retry. Attempt Close, read the warning and choose stay; require the report still open. Close again and explicitly Stop; require report disappearance and GDM. Restore Internet access through the same LIFE06 VM helper from the observed GDM surface; no Parent login is needed.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_confirm_stopping_a_sending_kiosk_report
```
