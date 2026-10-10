# 150k — Send an authorized kiosk error report

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED11, FEED09 success and FEED14 kiosk**. First scheduled consumer: [E2E-047, case 221](../E2E-Scenario-Recipes.md#e2e-047).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** Explicit sending authorization and the qualified public cooldown-error entry are both required.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.
- **187k** — REQUEST09 cooldown and FEED15 kiosk; gate in brief.

## Implementation

Bind one reviewed synthetic Send on the actual kiosk error-report window. Reuse the qualified public cooldown-error prefix and shared submission operation; qualify the surface's confirmation and exit separately from ordinary Parent feedback.

## Live VM acceptance

On the VM, produce the public error, review the report and Privacy, Send once, observe acceptance and keep thanks visible for five seconds. Dismiss normally and require report closure plus GDM. Opening or successful transport alone cannot satisfy exit behavior.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_send_an_authorized_kiosk_error_report
```
