# 296 — Observe Lunar command denial

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the original command's specific public policy denial and complete public absence result. Reuse 296c's launch/window/absence operations; tray controls, Minecraft and login intervals remain separate.

Reuse the delivered scope of task **296c** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02 Lunar original-AppImage command denial and complete public absence**. First complete consumer:
[E2E-052/case 253](../E2E-Scenario-Recipes.md#e2e-052).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296c** — Original-AppImage launch, owned Lunar window and complete public absence.
- **079** — Public saved match/access editing for the original Lunar path.

Its transitive prerequisites retain verified FIX05 Lunar/AppImageLauncher/autostart/
Minecraft assets and guarded TIME03 intervals.

## Implementation

Add the original AppImage command's specific denial result under the
[profile contract](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate).
Reuse 296c's command launch and owned-window/complete-absence observations
when composing the new policy branch. Task 296d's tray close/restore is needed
by allowed autostart, not by this command-denial qualification.
Apply the external-provider exception only in
explicit adapters, preserving owner, ambiguity and input/result checks. Keep
Minecraft gameplay and continuous login observation in their following tasks.

## Live VM acceptance

In fresh guarded attempts, qualify the original-AppImage command's specific
policy denial using the prepared rule path and complete public observations.
Reuse unchanged allowed launch/Quit and complete-absence qualification from
296c; rerun its affected branches when the shared adapter changes.
Qualify the independently supplied denied entry. Focused adapter checks cover
wrong owner, ambiguity, incomplete observations and uncertain-input refusal
without replay; keep the same runtime guards. Do not rerun the unchanged native
grid/command policy matrix or Lunar allowed/tray history. No process/rule probe
may supply a customer result.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_lunar_provider
```

Pass affected safety/adapter checks before the VM run. Use shared watch intent,
observation and transport throughout; require collection and owned cleanup.

APP06's game and login bindings remain pending; this task does not pass case 253.
