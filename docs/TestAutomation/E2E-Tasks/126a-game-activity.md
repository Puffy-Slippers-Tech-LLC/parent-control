# 126a — Install, launch and observe the real game

Estimate: 30–50 minutes for focused implementation and targeted live validation;
not a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FIX04 game asset; game APP01/02/03/04 and FLOW08**. First scheduled consumer: [E2E-023, case 126](../E2E-Scenario-Recipes.md#e2e-023).
Read only the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and that consumer's selected recipe.

Required implemented capabilities (IDs identify queue rows; no predecessor brief is needed):

- **006** — LIFE04 install only.
- **047** — APP04; FLOW08 native usable-app scope.

Use maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind one maintained real offline game, its verified asset and a reproducible level with accessible public state. Stage through FIX04 and install through the visible LIFE04 terminal route when needed. Qualify the game's APP01 launch, APP02 window, APP03 ordinary input/effect and APP04 recognizable activity in that order, then its FLOW08 usable branch. Keep mode/level composition and expiry in the later APP05/FLOW10 slice.

## Live VM acceptance

On the live VM, install the declared game if needed, enter a child with ample publicly prepared time, launch it and start the fixed level through explicit normal UI inputs. Play an action, independently observe its effect, capture recognizable progress and compare a fresh observation of the same window. An independently opened game at the declared level is also a valid entry. Wrong-window or missing prior-activity input refuses. Do not wait for expiry, substitute a timer/mock game or use private state. If choosing/installing the asset and adding its public adapters expose separate substantial work, split those scoped consumers before implementation.

Run affected safety/adapter checks, then the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_game_activity
```

The selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract).
Require independent valid entry, wrong-entry refusal and owned live VM cleanup.
Host checks and a diagnostic slice do not establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
If a complete E2E scenario passed, refresh coverage immediately after that case.
Use `tools/generate_test_coverage.sh`, which runs `tools/generate_test_coverage.py`.

Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and the selected family's status
in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md); leave unfinished scope pending.
Check **126a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
