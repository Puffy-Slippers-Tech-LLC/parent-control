# 187b — Observe and decline a kiosk cooldown error

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **REQUEST09 kiosk cooldown and FEED15 decline branch**. Named consumer: task **187k** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** The normal station re-entry-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021a** — Prepared kiosk request, real approval and automatic GDM return.

## Implementation

Qualify the normal kiosk reopen/re-entry and Request before the real five-second cooldown ends. Observe the actual too-soon result and decline reporting through owned controls. Preserve the existing public-route applicability gate.

Use the recipe's [bounded cooldown trigger](../E2E-Scenario-Recipes.md#pending-approval-and-account-changes):
ready station entry/observer before approval, then perform only necessary exit,
entry, child selection and Request with fresh guards. Read balances and inspect
the report after refusal. A missed window fails; do not loop Request or approvals.

Extend `kiosk_approved_flow.approved_request` / `onpc_request_flow::approve`,
`onpc_gdm::enter_station` and `AccessibleUI.kiosk_request_form` for the genuine
cooldown/result/report-choice binding. Existing request composites accept only
75 seconds with soft apps included; case 178 needs the explicit 30-second,
soft-excluded binding and cross-child refusal. FEED15's request-result branch
is planned. Declining needs neither Privacy nor a retained account visit, and
this slice ends without waiting or another approval.

## Live VM acceptance

Approve once on the VM, perform the normal return-and-Request within five seconds, read the error and decline. Independently observe the declared form/desktop or GDM destination and original balance before another approval. An unreachable route stays pending; no timing changes or forced errors.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_kiosk_cooldown_error
```
