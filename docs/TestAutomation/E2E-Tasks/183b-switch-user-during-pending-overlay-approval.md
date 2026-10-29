# 183b — Switch User during pending overlay approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 overlay Switch User**. First scheduled consumer: [E2E-039, case 172](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Use the shared system-session helper while the real approval prompt is pending.
A modal blocking Shell menus is not a gate. Independently observe the session
transition and cancelled request; do not substitute the prompt's Cancel action.
Case 172 owns the later fresh approval and complete access/recovery results.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048d** — Real overlay prompt and automatic successful approval/return.
- **043c** — Intended retained child's successful GDM reauthentication.

## Implementation

Compose only the overlay Switch User branch with an already observed real AUTH01
prompt and explicit pre-request choices/balances. Use the shared DESK03
lock/greeter command, observe GDM and return to the same retained child desktop.
Read REQUEST03 and require the old prompt absent and choices/balances unchanged
by cancellation.

Extend `request_flow.overlay_authentication`, `journey_blocks.desktop_entry`
and `onpc_desktop_session::enter_desktop` for this pending-prompt composition;
FLOW17 is unimplemented. Reuse their recipient/session guards and unchanged
retained-entry qualification, adding only transition/result and focused refusal
coverage for the new binding.

## Live VM acceptance

On the VM, supply usable time and a real pending approval, Switch User and return
through the qualified retained-child operation. Qualify the pending-prompt
transition, old-prompt absence, cancellation and usable request return with
unchanged choices/balances. Do not repeat a successful approval/recovery history
as this capability's prerequisite acceptance; case 172 retains it. Reuse
unchanged authentication and retained-entry qualification and focused guard
coverage. Cancellation consumes no cooldown; add no fixed wait.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_switch_user_during_pending_overlay_approval
```
