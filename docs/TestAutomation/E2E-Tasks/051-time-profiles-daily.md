# 051 — Compose the daily-only time profile

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW13 daily-only, fresh/same Parent entry with observed G=0**. First scheduled consumer: [E2E-008, case 21](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.
- **003** — DESK02, DESK03, DESK04.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the daily-only FLOW13 branch from fresh/same FLOW01, PARENT09, FLOW02 and DESK03. Require an already observed zero grant; refuse unexpected nonzero G. Optional revocation and retained Parent entry are qualified with the later grant-profile extension.

## Live VM acceptance

In a fresh installed VM attempt, reach Parent, read G=0, save a short positive allowance, verify D>0/G=0 and finish at GDM. Qualify an independently opened same-user Parent entry too. No real approval or retained-user return is required by this slice.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_time_profiles_daily
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
