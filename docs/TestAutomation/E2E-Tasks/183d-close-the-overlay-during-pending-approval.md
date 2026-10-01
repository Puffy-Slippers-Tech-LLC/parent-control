# 183d — Close the overlay during pending approval

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 overlay app-close**. First scheduled consumer: [E2E-039, case 174](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** The normal leave/close action must be reachable while the real prompt is pending. If the modal prevents it, leave this binding pending; signals, forced logout and agent Cancel cannot replace it.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **028** — LIFE01.
- **052c** — TIME03.

## Implementation

Compose only the overlay app-close branch with an already observed real AUTH01 prompt and explicit pre-request choices/balances. Use the supported normal requesting-app close action, then reopen through REQUEST02's direct child command. Cancel on the agent is not this route. Read REQUEST03 and require the old prompt absent; a later request must authenticate afresh.

## Live VM acceptance

On the VM, publicly prepare usable time, capture choices/balances, start approval and perform the declared action while authentication is pending. Observe the destination and return, inspect cancellation and original balances before another request, then require a new prompt. Use TIME03 only for the actual cooldown.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_close_the_overlay_during_pending_approval
```
