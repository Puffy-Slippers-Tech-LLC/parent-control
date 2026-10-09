# 065 — Compose the combined grant-dominant profile

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add combined/grant-dominant G>D>0 with its own fresh live preparation. Reuse 065a's grant-only and explicit-revoke branches.

Reuse the delivered scope of tasks **065a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **FLOW13 grant-only/combined; retained entry and explicit revoke preparation**. First scheduled consumer: [E2E-010, case 25](../E2E-Scenario-Recipes.md#e2e-010).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **065a** — FLOW13 grant-only profile and explicit revoke preparation.

## Implementation

Extend FLOW13 to combined/grant-dominant using 065a's real kiosk approval and retained Parent readback operations. Reuse its grant-only and explicit-revoke branches. Keep D/G meanings and elapsed/rounding margins explicit.

## Live VM acceptance

In a fresh guarded VM attempt, observe G>D>0 for the declared combined/grant-dominant preparation after real kiosk approval and retained Parent readback. Finish at GDM without changing the clock or disabling a live grant. Qualify independent valid entry and wrong-entry refusal; an unexpected existing grant without an explicit revoke-first action refuses instead of clearing it silently. When revoke-first is declared, reuse PARENT17/18 and fresh PARENT09 readback. Reuse 065a's unchanged exact grant-only and revoke-first qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_time_profiles_grant
```
