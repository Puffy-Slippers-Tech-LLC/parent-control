# 062 — Use an app until a natural enforced lock

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **TIME04**. First scheduled consumer: [E2E-008, case 21](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052a** — TIME02 minute/final-second ticks.
- **047** — APP04; FLOW08 native usable-app scope.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose bounded APP03 actions/TIME03 waits, TIME02 only while visible, and public lock/input-ownership observations. Receive earlier visible balance and deadline explicitly.

## Live VM acceptance

From daily-only time prepared through customer controls, use the actual app until natural exhaustion. Observe lock and a harmless key reaching the lock challenge while desktop interaction is unavailable. No manual Lock, backend expiry, or hidden-window inspection.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_natural_expiry
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
