# 296 — Qualify Lunar launch, tray and Quit

Estimate: 40–60 minutes; not a stop timer. Follow the
[master](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **APP06 snapshot and APP01/02/03/UI18 Lunar launch, tray and Quit bindings**. First complete consumer:
[E2E-052/case 253](../E2E-Scenario-Recipes.md#e2e-052).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **295** — FIX05; restored Lunar/AppImageLauncher/autostart/Minecraft prerequisites only. Blocker: profile and repeatable setup unqualified; resume when the manual assets and standard restore path are available..
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **052c** — TIME03.

## Implementation

Qualify the prepared original AppImage's command launch, Lunar window, close to
tray, tray restore and genuine Quit under the
[profile contract](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate).
Implement a bounded APP06 public snapshot of the tray/Lunar surfaces and the
recognized surrounding desktop. Apply the external-provider exception only in
explicit adapters, preserving owner, ambiguity and input/result checks. Keep
Minecraft gameplay and continuous login observation in their following tasks.

## Live VM acceptance

In fresh guarded attempts, qualify allowed original-AppImage launch, close to
tray, restore, Quit and independent absence with a complete surrounding desktop.
Qualify the same command's specific policy denial using the prepared rule path.
Exercise independently supplied valid entry, wrong owner, ambiguity, incomplete
observations and uncertain-input refusal without replay. No process/rule probe
may supply a customer result.

Implement and register this fixed qualification in the existing envelope:

```sh
tools/run-tests integration check_e2e_lunar_provider
```

Pass affected safety/adapter checks before the VM run. Use shared watchvm intent,
observation and transport throughout; require collection and owned cleanup.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record exact qualified callables and scope, check **296** after cleanup, advance
the single pointer and delete this brief. APP06's game and login bindings remain
pending; this task does not pass case 253.
