# 187o — Review an overlay cooldown report

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add review-report entry, Privacy and normal report-close destination. Reuse 187a's actual cooldown trigger and unchanged independently qualified decline result.

Reuse the delivered scope of tasks **187a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **REQUEST09 cooldown and FEED15 overlay**. First scheduled consumer: [E2E-039, case 176](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** The normal overlay reopen-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **187a** — REQUEST09 overlay cooldown and FEED15 decline branch; gate in brief.

## Implementation

Reuse 187a's public reopen/Request and selected-parent approval operations to reach the actual five-second cooldown error. Add report-review, Privacy and normal report-close bindings with their overlay destinations; never extend product timing.

## Live VM acceptance

In a fresh guarded VM attempt, approve once, reopen and Request before five seconds from success, and read the actual too-soon result. Review the report, visit Privacy and close normally; independently check the report/form destination and original balance before any new approval. Qualify independent valid entry and wrong-surface/owner refusal. Reuse 187a's unchanged exact decline qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state. An unreachable public trigger remains pending.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_read_overlay_cooldown_errors_and_report_choices
```
