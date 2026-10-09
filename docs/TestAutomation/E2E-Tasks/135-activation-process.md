# 135 — Follow a real process-activation update

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: Real update activation and the affected mechanical package checks remain required alongside the narrowed process branch.

## Session boundary

Add the process-activation profile, notice and normal affected-app close/reopen sequence. Reuse 135a's fixed update/result infrastructure while retaining distinct live evidence for both profiles.

Reuse the delivered scope of tasks **135a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **LIFE04 update; LIFE05 process/none scope**. First scheduled consumer: [E2E-026, case 136](../E2E-Scenario-Recipes.md#e2e-026).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **135a** — LIFE04 update and LIFE05 no-action notice.

Its transitive prerequisites retain normal app restart, retained-desktop routing,
customer reboot, public app-policy editing and overlay request entry/results/exits.

## Implementation

Bind a verified old/new package profile requiring process activation. Extend LIFE04(update) and LIFE05 only for this process route; reuse 135a's unchanged no-action branch. Follow the displayed requirement for every named affected app/user; preserve all mechanical migration obligations.

## Live VM acceptance

On the VM install the real process-activation update, read its requirement,
perform the normal affected-app close/reopen sequence and independently read
retained settings before edits. Reuse unchanged no-action qualification from
135a; rerun it when shared changes affect that branch. Both claimed LIFE05
branches retain scoped live evidence. Run affected package activation checks
separately.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_activation_process
```
