# 062 — Use an app until a natural enforced lock

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **TIME04**. First scheduled consumer: [E2E-008, case 21](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **052a** — TIME02 minute/final-second ticks.
- **047** — APP04; FLOW08 native usable-app scope.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose bounded APP03 actions/TIME03 waits, TIME02 only while visible, and public lock/input-ownership observations. Receive earlier visible balance and deadline explicitly.

## Live VM acceptance

From daily-only time prepared through customer controls, use the actual app until natural exhaustion. Observe lock and a harmless key reaching the lock challenge while desktop interaction is unavailable. No manual Lock, backend expiry, or hidden-window inspection.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_expiry
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
