# 126a — Launch and observe the prepared offline game

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **Game APP01/02/03/04 and FLOW08 usable activity**. First scheduled consumer: [E2E-023, case 126](../E2E-Scenario-Recipes.md#e2e-023).
Read only the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and that consumer's selected recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **126p** — FIX04 game asset; LIFE04 fixed game installation profile.
- **047** — APP04; FLOW08 native usable-app scope.

Use maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the fixed installed game profile from task 126p. Qualify APP01 launch,
APP02 window identity, APP03 ordinary input/effect and APP04 recognizable activity,
then compose its FLOW08 usable branch. Repository-owned controls use public IDs.
Keep installation, mode/level composition and natural expiry in their own tasks.

## Live VM acceptance

On the live VM, install the declared game if needed, enter a child with ample publicly prepared time, launch it and start the fixed level through explicit normal UI inputs. Play an action, independently observe its effect, capture recognizable progress and compare a fresh observation of the same window. An independently opened game at the declared level is also a valid entry. Wrong-window or missing prior-activity input refuses. Do not wait for expiry, substitute a timer/mock game or use private state. If choosing/installing the asset and adding its public adapters expose separate substantial work, split those scoped consumers before implementation.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_game_activity
```

The selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract).
Require independent valid entry, wrong-entry refusal and owned live VM cleanup.
Host checks and a diagnostic slice do not establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **126a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
