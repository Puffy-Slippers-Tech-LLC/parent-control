# 187k — Review a kiosk cooldown report

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add review-report entry, Privacy and normal report-close destination. Reuse 187b's actual cooldown trigger and unchanged independently qualified decline result.

Reuse the delivered scope of tasks **187b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **REQUEST09 cooldown and FEED15 kiosk**. First scheduled consumer: [E2E-039, case 178](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** The normal station re-entry-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **187b** — REQUEST09 kiosk cooldown and FEED15 decline branch; gate in brief.
- **030** — Shared in-app Privacy disclosure and preserved-draft comparison; qualify the station binding here.

## Implementation

Reuse 187b's station re-entry, Request and approval operations to reach the real five-second cooldown error. Add report-review, Privacy and normal report-close bindings with the correct station/GDM destination. Do not change timing or force an error.

Reuse the recipe's [bounded cooldown trigger](../E2E-Scenario-Recipes.md#pending-approval-and-account-changes)
without inserting report/balance reads between approval and Request. Report
review follows the observed refusal and has no five-second completion deadline.

Use `parent_reports.report_review`, `onpc_feedback_privacy::review_privacy`
and `AccessibleUI.feedback_snapshot` as shared extension points; their current
report/Privacy projections are Parent-bound. Add the station projection and
cross-child cooldown result, preserving station restrictions and focused
ownership refusals without repeating Parent or decline qualification histories.

## Live VM acceptance

In a fresh guarded VM attempt, approve once, re-enter and select the other child,
then Request before five seconds from success and read the too-soon result.
Review its report, visit Privacy and close normally; independently check the
station/GDM destination and both children's original balances before later
approval. Qualify independent valid entry and wrong-child/surface/owner refusal.
Reuse 187b's unchanged exact decline qualification, rerunning affected branches
when necessary; its evidence supplies no saved VM state. An unreachable public
trigger remains pending. Case 178 retains review and decline in its complete
journey with separate cooldown errors.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_read_station_cooldown_errors_and_report_choices
```
