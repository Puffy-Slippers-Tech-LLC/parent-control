# 183b — Switch User during pending overlay approval

Estimate: 25–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW17 overlay Switch User**. First scheduled consumer: [E2E-039, case 172](../E2E-Scenario-Recipes.md#e2e-039).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

**Gate:** The normal leave/close action must be reachable while the real prompt is pending. If the modal prevents it, leave this binding pending; signals, forced logout and agent Cancel cannot replace it.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose only the overlay Switch User branch with an already observed real AUTH01 prompt and explicit pre-request choices/balances. Use the offered session controls to Switch User, observe GDM and return to the same retained child desktop. Read REQUEST03 and require the old prompt absent; a later request must authenticate afresh.

## Live VM acceptance

On the VM, publicly prepare usable time, capture choices/balances, start approval and perform the declared action while authentication is pending. Observe the destination and return, inspect cancellation and original balances before another request, then require a new prompt. Use TIME03 only for the actual cooldown.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_switch_user_during_pending_overlay_approval
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
