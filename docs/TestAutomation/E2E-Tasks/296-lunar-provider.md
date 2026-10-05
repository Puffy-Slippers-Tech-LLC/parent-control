# 296 — Observe Lunar command denial

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the original command's specific public policy denial and compose the complete snapshot/launch/tray/Quit contract. Reuse 296c/296d; Minecraft and login intervals remain separate.

Reuse the delivered scope of tasks **296c**, **296d** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP06 snapshot and APP01/02/03/UI18 Lunar launch, tray and Quit bindings**. First complete consumer:
[E2E-052/case 253](../E2E-Scenario-Recipes.md#e2e-052).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **295** — FIX05; restored Lunar/AppImageLauncher/autostart/Minecraft prerequisites only.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **052c** — TIME03.
- **296d** — APP06 Lunar/tray snapshot and close-to-tray/restore.

## Implementation

Add the original AppImage command's specific denial result under the
[profile contract](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate).
Reuse 296c/296d's command launch, Lunar window, close-to-tray, restore, Quit and
APP06 surrounding-desktop snapshots when composing the new policy branch.
Apply the external-provider exception only in
explicit adapters, preserving owner, ambiguity and input/result checks. Keep
Minecraft gameplay and continuous login observation in their following tasks.

## Live VM acceptance

In fresh guarded attempts, qualify the original-AppImage command's specific
policy denial using the prepared rule path and complete public observations.
Reuse unchanged allowed launch/Quit and tray/restore results from 296c/296d;
rerun their affected branches when the shared adapter changes.
Exercise independently supplied valid entry, wrong owner, ambiguity, incomplete
observations and uncertain-input refusal without replay. No process/rule probe
may supply a customer result.

Implement and register this fixed qualification in the existing envelope:

```sh
tools/run-tests integration check_e2e_lunar_provider
```

Pass affected safety/adapter checks before the VM run. Use shared watch intent,
observation and transport throughout; require collection and owned cleanup.

APP06's game and login bindings remain pending; this task does not pass case 253.
