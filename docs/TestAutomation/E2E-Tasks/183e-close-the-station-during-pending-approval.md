# 183e — Close the station during pending approval

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW17 kiosk app-close**. First scheduled consumer: [E2E-039, case 175](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** The normal leave/close action must be reachable while the real prompt is pending. If the modal prevents it, leave this binding pending; signals, forced logout and agent Cancel cannot replace it.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **020** — AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits.
- **014** — FLOW04 kiosk.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose only the kiosk app-close branch with an already observed real AUTH01 prompt and explicit pre-request choices/balances. Use the supported normal station close action, observe GDM, then re-enter the station. Cancel on the agent is not this route. Read REQUEST03 and require the old prompt absent; a later request must authenticate afresh.

## Live VM acceptance

On the VM, publicly prepare usable time, capture choices/balances, start approval and perform the declared action while authentication is pending. Observe the destination and return, inspect cancellation and original balances before another request, then require a new prompt. Use TIME03 only for the actual cooldown.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_close_the_station_during_pending_approval
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
