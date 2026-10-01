# 189k — Send a kiosk report without unavailable logs

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED11 without-logs and FEED09/14 kiosk result**. First scheduled consumer: [E2E-046, case 213](../E2E-Scenario-Recipes.md#e2e-046).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

**Gate:** The genuine public collection-failure route and explicit authorization for this synthetic submission must be available. Successful collection recovery/Retry is not a prerequisite.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **188k** — FEED09 kiosk collection failure and usable controls; gate in brief.
- **150** — FEED11, FEED09 sending/success and FEED14 Parent feedback; gate in brief.

## Implementation

Bind the explicit Send without logs action on kiosk after observed collection failure and reviewed FEED03/FEED05 evidence. Qualify its actual acceptance and confirmation destination; use one input and no automatic retry by the test.

## Live VM acceptance

With the reviewed sending authorization, reproduce the qualified public collection failure on the VM, submit the declared report once without logs, observe service acceptance, dismiss thanks and require the kiosk-specific final destination. Missing logs alone is not acceptance.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_send_a_kiosk_report_without_unavailable_logs
```
