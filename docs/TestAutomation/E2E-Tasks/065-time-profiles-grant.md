# 065 — Compose the combined grant-dominant profile

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add combined/grant-dominant G>D>0 with its own fresh live preparation. Reuse 065a's grant-only and explicit-revoke branches.

Tasks **065a** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **FLOW13 grant-only/combined; retained entry and explicit revoke preparation**. First scheduled consumer: [E2E-010, case 25](../E2E-Scenario-Recipes.md#e2e-010).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **051** — FLOW13 daily-only, fresh/same Parent entry with observed G=0.
- **050** — PARENT17, PARENT18.
- **065a** — FLOW13 grant-only profile and explicit revoke preparation.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend FLOW13 to grant-only and combined/grant-dominant using real kiosk approval followed by retained Parent readback. Keep D/G meanings and elapsed/rounding margins explicit.

## Live VM acceptance

On independent VM attempts, observe D=0/G>0 for grant-only and G>D>0 for the declared combined/grant-dominant preparation. Finish at GDM each time without changing the clock or disabling a live grant. Qualify the explicitly requested revoke-first preparation with PARENT17/18 and fresh PARENT09 readback; an unexpected existing grant without that declared action refuses instead of clearing it silently.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_time_profiles_grant
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
