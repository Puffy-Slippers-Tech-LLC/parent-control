# 129 — Play fullscreen to natural lock

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP05/FLOW10 fullscreen play**. First scheduled consumer: [E2E-023, case 127](../E2E-Scenario-Recipes.md#e2e-023).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **126** — APP05/FLOW10 windowed game.

## Implementation

Extend the real game's shared mode/level preparation and ordinary input observations to fullscreen. Use supported launch options or its fixed fullscreen shortcut and independently observe the result; do not automate game settings menus for preparation. Keep countdown reads conditional on public visibility during play. Reuse the bounded natural-expiry loop.

`onpc_test_application.c::main` and `gui_application.py::main` currently expose
no fullscreen option/shortcut or public mode projection. Add one supported
finite game-mode operation and independent result to that existing fixture
before this consumer, retaining its actual move/score activity. `FixtureUI`'s
game kind alone supplies no fullscreen proof. Reuse 126's unchanged windowed
launch/activity and TIME04 guards; qualify only fullscreen gameplay and its
natural-lock composition, without rerunning the full windowed history.

## Live VM acceptance

On the live VM, prepare fullscreen and the declared level through the shared command/shortcut route, then observe actual gameplay input/effects. Play to natural lock and prove normal input belongs to the lock. Do not require a Shell panel or visible countdown while the game hides them.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_game_fullscreen
```
