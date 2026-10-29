# 183a — Lock during pending overlay approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 overlay lock**. First scheduled consumer: [E2E-039, case 171](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Use the shared system-session helper while the real approval prompt is pending.
A modal blocking Shell menus is not a gate. Independently observe the session
transition and cancelled request; do not substitute the prompt's Cancel action.
Case 171 owns the later fresh approval and complete access/recovery results.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048d** — Real overlay prompt and automatic successful approval/return.
- **043c** — Intended child's successful direct lock-screen unlock.

## Implementation

Compose only the overlay lock branch with an already observed real AUTH01 prompt
and explicit pre-request choices/balances. Use the normal lock shortcut, observe
the lock challenge and unlock legitimately. Read REQUEST03 and require the old
prompt absent and choices/balances unchanged by cancellation.

Extend `request_flow.overlay_authentication` and the shared
`onpc_desktop_session::lock` / `unlock_success` operations for the pending-prompt
composition. Their current bindings do not implement FLOW17. Keep the valid
recipient and single-use input guards; qualify the new transition and focused
refusals without replaying the unchanged Cancel/rejection/exit histories.

## Live VM acceptance

On the VM, supply usable time and a real pending approval, lock and return through
the qualified retained-child operation. Qualify the pending-prompt transition,
old-prompt absence, cancellation and usable request return with unchanged
choices/balances. Do not repeat a successful approval/recovery history as this
capability's prerequisite acceptance; case 171 retains it. Reuse unchanged
authentication and lock/unlock qualification and focused guard coverage.
Cancellation consumes no cooldown; add no fixed wait.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_lock_during_pending_overlay_approval
```
