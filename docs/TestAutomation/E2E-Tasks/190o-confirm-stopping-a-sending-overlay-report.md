# 190o — Stop a sending overlay report

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
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

- **190a** — FEED09 retry and FEED17/18 overlay stay-open branch; gate in brief.

## Implementation

Reuse 190a's authorized retry-entry and FEED17 warning operations, then add FEED18 Stop sending and close with its exact child-desktop destination. Preserve the warning that stopping cannot recall an already accepted request.

## Live VM acceptance

In a fresh guarded VM attempt with an authorized synthetic report reached through its public error, use LIFE06 to remove Internet access, Send once and observe retry. Attempt Close, read the warning and explicitly Stop; independently require report disappearance and the child desktop. Qualify independent valid retry entry and wrong-surface/owner refusal without replaying Send. Restore Internet access through the same LIFE06 VM helper from the observed child desktop; no Parent visit is needed. Reuse 190a's unchanged exact stay-open qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state. Case 218 retains the complete stay-open followed by Stop history.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_confirm_stopping_a_sending_overlay_report
```
