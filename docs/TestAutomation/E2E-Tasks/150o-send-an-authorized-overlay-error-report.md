# 150o — Send an authorized overlay error report

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED11, FEED09 success and FEED14 overlay**. First scheduled consumer: [E2E-047, case 220](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** Explicit sending authorization and the qualified public cooldown-error entry are both required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **187o** — REQUEST09 cooldown and FEED15 overlay; gate in brief.

## Implementation

Bind one reviewed synthetic Send, including the reviewed synthetic reply address,
on the actual overlay error-report window. Reuse the qualified public cooldown-error
prefix and shared submission operation; qualify the surface's confirmation,
reply-follow-up note and exit separately from ordinary Parent feedback.

## Live VM acceptance

On the VM, produce the public error, review the report and Privacy, Send once, observe acceptance and keep thanks visible for five seconds. Dismiss normally and require report closure plus the child desktop. Opening or successful transport alone cannot satisfy exit behavior.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_send_an_authorized_overlay_error_report
```
