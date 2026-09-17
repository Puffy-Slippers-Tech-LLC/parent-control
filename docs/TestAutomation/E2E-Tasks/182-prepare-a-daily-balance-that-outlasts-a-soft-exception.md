# 182 — Prepare a daily balance that outlasts a soft exception

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FLOW18**. First scheduled consumer: [E2E-038, case 164](../E2E-Scenario-Recipes.md#e2e-038).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.
- **079b** — FLOW19.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **052a** — TIME02 minute/final-second ticks.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose the exact daily-dominant-with-soft-exception recipe from qualified profiles, app use, retained Parent readback and TIME03. Do not edit allowance or app policy after approval; such edits restore launch blocks.

## Live VM acceptance

On the live VM, approve the prescribed small addition with soft apps, open S, switch away and wait while daily use pauses. Read G in the 60–90-second window and D at least 120 seconds, then return while G remains positive. Wrong inequalities fail preparation; no relabeling or top-up.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_expired_soft
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
