# 126a — Launch and observe the prepared offline game

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Game APP01/02/03/04 and FLOW08 usable activity**. First scheduled consumer: [E2E-023, case 126](../E2E-Scenario-Recipes.md#e2e-023).
Read only the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and that consumer's selected recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **126p** — Offline-game baseline assets and verification; FIX04 transfer only.
- **047** — APP04; FLOW08 native usable-app scope.

Use maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the fixed installed game profile from task 126p. Qualify APP01 launch,
APP02 window identity, APP03 ordinary input/effect and APP04 recognizable activity,
then compose its FLOW08 usable branch. Repository-owned controls use public IDs.
Keep installation, mode/level composition and natural expiry in their own tasks.

## Live VM acceptance

On the live VM, verify the declared baseline game without repair, enter a child with ample publicly prepared time, and launch the fixed game/level through shared supported commands or shortcuts. Perform a real gameplay input, independently observe its effect, capture recognizable progress and compare a fresh observation of the same window. An independently opened game at the declared level is also a valid entry. Wrong-window or missing prior-activity input refuses. Do not wait for expiry, substitute a timer/mock game or use private state. Reuse 126p's existing offline game and one fixed level; this task does not choose another game or repeat installation qualification. One ordinary play action and its visible effect establish usability; do not add level completion, score targets, game-mechanics coverage or an automated gameplay strategy.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_game_activity
```

The selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract).
Require independent valid entry, wrong-entry refusal and owned live VM cleanup.
Host checks and a diagnostic slice do not establish complete scenario coverage.

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
