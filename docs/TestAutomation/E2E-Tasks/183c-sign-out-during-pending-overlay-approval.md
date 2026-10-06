# 183c — Sign out during pending overlay approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 overlay sign-out**. First scheduled consumer: [E2E-039, case 173](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Use the shared system-session helper for this lock, switch-user or logout action while the real approval prompt is pending. A modal blocking Shell menus is not a gate. Independently observe the session transition, cancelled request and later fresh request; do not substitute the approval prompt's Cancel action.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.

## Implementation

Compose only the overlay sign-out branch with an already observed real AUTH01 prompt and explicit pre-request choices/balances. Use DESK04's shared `gnome-session-quit --logout --no-prompt` command, independently observe ended-session/GDM entry, then perform a fresh child login. Do not claim old-window continuity. Read REQUEST03 and require the old prompt absent; a later request must authenticate afresh.

## Live VM acceptance

On the VM, publicly prepare usable time, capture choices/balances, start approval and perform the declared action while authentication is pending. Observe the destination and return, inspect cancellation and original balances before another request, then require a new prompt. Use TIME03 only for the actual cooldown.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_sign_out_during_pending_overlay_approval
```
