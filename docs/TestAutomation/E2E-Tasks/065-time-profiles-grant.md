# 065 — Compose grant-only and combined time profiles

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW13 grant-only/combined; retained entry and explicit revoke preparation**. First scheduled consumer: [E2E-010, case 25](../E2E-Scenario-Recipes.md#e2e-010).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **051** — FLOW13 daily-only, fresh/same Parent entry with observed G=0.
- **050** — PARENT17, PARENT18.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend FLOW13 to grant-only and combined/grant-dominant using real kiosk approval followed by retained Parent readback. Keep D/G meanings and elapsed/rounding margins explicit.

## Live VM acceptance

On independent VM attempts, observe D=0/G>0 for grant-only and G>D>0 for the declared combined/grant-dominant preparation. Finish at GDM each time without changing the clock or disabling a live grant.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_time_profiles_grant
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
