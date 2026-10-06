# 187o — Review an overlay cooldown report

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add review-report entry, Privacy and normal report-close destination. Reuse 187a's actual cooldown trigger and decline result; preserve independent attempts for both outcomes.

Reuse the delivered scope of tasks **187a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **REQUEST09 cooldown and FEED15 overlay**. First scheduled consumer: [E2E-039, case 176](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

**Gate:** The normal overlay reopen-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.
- **030** — FEED05; FEED10 dialog persistence.
- **187a** — REQUEST09 overlay cooldown and FEED15 decline branch; gate in brief.

## Implementation

Qualify the public reopen/Request route within the actual five-second cooldown, then report-review/decline bindings and their overlay destinations. Reuse selected-parent approval; never extend product timing.

## Live VM acceptance

On the VM, approve once, reopen and Request before five seconds from success, and read the actual too-soon result. In independent attempts review and decline reporting, checking form/report destinations and original balance before any new approval.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_read_overlay_cooldown_errors_and_report_choices
```
