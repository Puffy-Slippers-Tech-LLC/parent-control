# 187k — Review a kiosk cooldown report

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add review-report entry, Privacy and normal report-close destination. Reuse 187b's actual cooldown trigger and decline result; preserve independent attempts for both outcomes.

Reuse the delivered scope of tasks **187b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **REQUEST09 cooldown and FEED15 kiosk**. First scheduled consumer: [E2E-039, case 177](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** The normal station re-entry-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.
- **030** — FEED05; FEED10 dialog persistence.
- **187b** — REQUEST09 kiosk cooldown and FEED15 decline branch; gate in brief.

## Implementation

Qualify station re-entry and Request within the real five-second cooldown, then review/decline bindings with the correct station/GDM destination. Do not change timing or force an error.

## Live VM acceptance

On the VM, approve once, re-enter and Request before five seconds from success, then read the too-soon result. Independently review and decline its report; read original balances before later approval. Other-child cooldown is bound by its separate case.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_read_station_cooldown_errors_and_report_choices
```
