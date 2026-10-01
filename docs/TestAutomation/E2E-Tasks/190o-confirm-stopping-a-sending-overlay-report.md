# 190o — Stop a sending overlay report

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add Stop sending and close, independently observing the child desktop. Reuse 190a's retry/warning/stay branch. Preserve the warning that stopping cannot recall an already accepted request and restore connectivity.

Reuse the delivered scope of tasks **190a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **FEED09 retry and FEED17/18 overlay**. First scheduled consumer: [E2E-047, case 218](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** Authorization for the submission, public cooldown-error entry and safe normal connectivity control are required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150o** — FEED11, FEED09 success and FEED14 overlay; gate in brief.
- **152** — FEED09 Parent retry/recovery over qualified LIFE06; gate in brief.
- **190a** — FEED09 retry and FEED17/18 overlay stay-open branch; gate in brief.

## Implementation

Bind retry on the overlay report after LIFE06 removes the VM's Internet access, then implement FEED17 before FEED18. Declare stay-open and Stop sending and close responses and their exact destinations; stopping cannot recall an already accepted request.

## Live VM acceptance

On the VM with an authorized synthetic report, use LIFE06 to remove Internet access, Send once and observe retry. Attempt Close, read the warning and choose stay; require the report still open. Close again and explicitly Stop; require report disappearance and the child desktop. Restore Internet access through the same LIFE06 VM helper from the observed child desktop; no Parent visit is needed.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_confirm_stopping_a_sending_overlay_report
```
