# 186 — Review a rejected Parent rule's report

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **PARENT15 failed-save; FEED15 Parent and report-close binding**. First scheduled consumer: [E2E-045, case 205](../E2E-Scenario-Recipes.md#e2e-045).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **078** — PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts.
- **030** — FEED05; FEED10 dialog persistence.

## Implementation

First extend PARENT15 for the recipe's rejected different-directory wildcard and automatic error report. Then bind FEED15 review, public action availability and normal UI18 closure. Parent has no Report this error toggle.

## Live VM acceptance

On installed Parent, submit the declared rejected pattern, read the real error/report, inspect the synthetic draft and Privacy, close the report and reread the last confirmed policy. Preserve the documented precise-override reload limitation rather than claiming an unsupported round trip.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_review_a_rejected_parent_rule_s_report
```
