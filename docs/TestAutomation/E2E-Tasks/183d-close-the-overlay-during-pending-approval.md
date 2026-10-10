# 183d — Close the overlay during pending approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 overlay app-close**. First scheduled consumer: [E2E-039, case 174](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** The normal leave/close action must be reachable while the real prompt is pending. If the modal prevents it, leave this binding pending; signals, forced logout and agent Cancel cannot replace it.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048d** — Real overlay prompt and automatic successful approval/return.

## Implementation

Compose only the overlay app-close branch with an already observed real AUTH01
prompt and explicit pre-request choices/balances. Use the shared Application UI
API surface `close` operation on the owned `kiosk-request-window`, preserving
its normal busy/modal refusal, then reopen through REQUEST02's direct child
command. Cancel on the agent is not this route. Read REQUEST03 through the same
API facade and require the old external prompt absent; a later request must
authenticate afresh.

Extend `request_flow.overlay_authentication`, `onpc_request_flow::overlay_entry`
and the shared API surface-close operation; FLOW17 has no callable yet. Parent
LIFE01 restarts and retained-account visits do not implement this overlay route.
Keep busy/modal refusal as the applicability gate and add focused new-binding
safety coverage instead of repeating unchanged authentication histories.

## Live VM acceptance

On the VM, publicly prepare usable time, capture choices/balances, start approval and close the overlay through the declared public route while authentication is pending. Observe disappearance and normal reopening, inspect cancellation and original balances before another request, then require fresh authentication and its successful time result. Cancellation consumes no cooldown; add no fixed wait.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_close_the_overlay_during_pending_approval
```
