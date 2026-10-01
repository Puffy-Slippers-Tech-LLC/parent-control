# 129 — Play fullscreen to natural lock

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP05/FLOW10 fullscreen play**. First scheduled consumer: [E2E-023, case 127](../E2E-Scenario-Recipes.md#e2e-023).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **126** — APP05/FLOW10 windowed game.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend the real game's shared mode/level preparation and ordinary input observations to fullscreen. Use supported launch options or its fixed fullscreen shortcut and independently observe the result; do not automate game settings menus for preparation. Keep countdown reads conditional on public visibility during play. Reuse the bounded natural-expiry loop.

## Live VM acceptance

On the live VM, prepare fullscreen and the declared level through the shared command/shortcut route, then observe actual gameplay input/effects. Play to natural lock and prove normal input belongs to the lock. Do not require a Shell panel or visible countdown while the game hides them.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_game_fullscreen
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
