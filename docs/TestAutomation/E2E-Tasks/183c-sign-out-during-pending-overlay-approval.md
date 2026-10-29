# 183c — Sign out during pending overlay approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 overlay sign-out**. First scheduled consumer: [E2E-039, case 173](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Use the shared system-session helper while the real approval prompt is pending.
A modal blocking Shell menus is not a gate. Independently observe the session
transition and cancelled request; do not substitute the prompt's Cancel action.
Case 173 owns the later fresh approval and complete access/recovery results.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048d** — Real overlay prompt and automatic successful approval/return.
- **003d** — Bound user's normal logout and independent ended-session/GDM result.

## Implementation

Compose only the overlay sign-out branch with an already observed real AUTH01
prompt and explicit pre-request choices/balances. Use DESK04's shared
`gnome-session-quit --logout --no-prompt` command, independently observe
ended-session/GDM entry, then perform a fresh child login. Do not claim old-window
continuity. Read REQUEST03 and require the old prompt absent and choices/balances
unchanged by cancellation.

Extend `request_flow.overlay_authentication`, `session_control.execute` and
`journey_blocks.desktop_entry` / `onpc_desktop_session::enter_desktop` for this
pending-prompt composition. FLOW17 is unimplemented; preserve command/source
identity, fresh-login recipient and no-replay guards. Retained-child visits and
the unchanged approval/refusal histories are not this slice's qualification.

## Live VM acceptance

On the VM, supply usable time and a real pending approval, sign out and return
through the qualified fresh-child operation. Qualify ended-session/GDM,
old-prompt absence, cancellation and usable request return with unchanged
choices/balances. Do not repeat a successful approval/recovery history as this
capability's prerequisite acceptance; case 173 retains it. Reuse unchanged
authentication, logout and fresh-entry qualification and focused guard coverage.
Cancellation consumes no cooldown; add no fixed wait.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_sign_out_during_pending_overlay_approval
```
