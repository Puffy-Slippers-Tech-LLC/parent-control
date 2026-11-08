# 187a — Observe and decline an overlay cooldown error

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **REQUEST09 overlay cooldown and FEED15 decline branch**. Named consumer: task **187o** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** The normal overlay reopen-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048d** — Real overlay approval and automatic return before reopening.

## Implementation

Qualify the normal overlay reopen/re-entry and Request before the real five-second cooldown ends. Observe the actual too-soon result and decline reporting through owned controls. Preserve the existing public-route applicability gate.

Use the recipe's [bounded cooldown trigger](../E2E-Scenario-Recipes.md#pending-approval-and-account-changes):
ready the shared reopen/observer before approval, then perform only necessary
return, reopen and Request with fresh guards. Read balances and inspect the
report after refusal. A missed window fails; do not loop Request or approvals.

Extend `request_flow.overlay_approved_request` / `onpc_request_flow::overlay_approve`
and `AccessibleUI.kiosk_request_form` with the genuine cooldown/result/report-choice
binding. Reuse the existing caller-bound request choices for case 176's
30-second, soft-excluded approval; those values are already supported by
`prepared_request(initial='observed', surface='overlay')` and
`overlay_approved_request`. Their existing worker guards do not admit a cooldown
journey, and no cooldown result is qualified by those approval bindings.
FEED15's request-result branch is planned. Declining needs neither Privacy nor a
retained account visit, and this slice ends without waiting or another approval.

## Live VM acceptance

Approve once on the VM, perform the normal return-and-Request within five seconds, read the error and decline. Independently observe the declared form/desktop or GDM destination and original balance before another approval. An unreachable route stays pending; no timing changes or forced errors.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_overlay_cooldown_error
```
