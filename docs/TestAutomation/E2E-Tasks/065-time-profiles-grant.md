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

- **051** — FLOW13 daily-only, fresh/same Parent entry with observed G=0.
- **050** — PARENT17, PARENT18.
- **065a** — FLOW13 grant-only profile and explicit revoke preparation.

## Implementation

Extend FLOW13 to grant-only and combined/grant-dominant using real kiosk approval followed by retained Parent readback. Keep D/G meanings and elapsed/rounding margins explicit.

## Live VM acceptance

On independent VM attempts, observe D=0/G>0 for grant-only and G>D>0 for the declared combined/grant-dominant preparation. Finish at GDM each time without changing the clock or disabling a live grant. Qualify the explicitly requested revoke-first preparation with PARENT17/18 and fresh PARENT09 readback; an unexpected existing grant without that declared action refuses instead of clearing it silently.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_time_profiles_grant
```
