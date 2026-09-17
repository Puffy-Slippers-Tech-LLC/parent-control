# 166 — Suspend and wake through normal controls

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **LIFE03**. First scheduled consumer: [E2E-022, case 124](../E2E-Scenario-Recipes.md#e2e-022).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **052a** — TIME02 minute/final-second ticks.
- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose system controls, guarded real wait, supported wake input and observed actual return surface. Keep subsequent unlock separate; retained activity comparisons require successful legitimate access.

## Live VM acceptance

In separate VM attempts, use FLOW13 to prepare a real active grant with zero daily allowance. Suspend normally and wake through supported input, once before and once after that grant's elapsed deadline. Observe the actual lock/desktop and use DESK08 to require successful access or specific time-limit denial. Suspended daily usage alone cannot prepare elapsed-time denial.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_suspend
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
