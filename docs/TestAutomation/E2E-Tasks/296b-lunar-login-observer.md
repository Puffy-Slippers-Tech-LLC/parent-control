# 296b — Prove the denied Lunar login interval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 40–60 minutes.

Session exception: The complete denied login interval, same-route denial control and shared recorder/secret regressions remain required.

## Session boundary

Add the complete denied login interval and same-route explicit denial control. Reuse 296f's observer lifecycle; transient usable surfaces must fail and case 253 stays pending.

Reuse the delivered scope of tasks **296f** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP06/UI22 continuous login interval and Lunar autostart binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296f** — APP06/UI22 allowed continuous login interval.
- **296** — Original-AppImage same-route specific policy denial.

Its transitive prerequisites retain public Minecraft surface identity, customer
reboot, the UI22 observer, distinct single-use login challenges, guarded TIME03
intervals and public Parent allowance preparation.

## Implementation

Compose 296f's newly qualified login observer with the separately qualified
Lunar/tray and Minecraft observations and existing login/reboot recorder. Arm before child login submission,
preserve secret sealing, and observe tray, Lunar and game surfaces until 90 seconds
after desktop readiness. Qualify reattachment before the first possible surface;
no blind interval or final-window-only absence claim is acceptable. Reuse the
shared observer, command transport and VM lease; no new capture loop or viewer.

## Live VM acceptance

On the guarded VM, qualify a complete denied login interval, with a real
original-AppImage launch and specific public denial
as the negative control. Missing samples, ambiguous ownership and transient usable
surfaces must fail. Pass applicable recorder/secret/cleanup tests and the master's
retained regressions. Reuse 296f's unchanged allowed-autostart qualification;
repeat that live branch only when shared changes affect it. Its evidence supplies
no saved VM state. This slice does not register or pass complete case 253.

Exercise new denied-interval/incomplete-sample/reattachment refusal in focused
harness coverage. Reuse unchanged credential-recipient, allowed observer,
Lunar/tray and Minecraft-entry qualification; do not add local-world play or
repeat their full histories solely to qualify this negative observation.

Implement and register the following planned fixed qualification before use:

```sh
tools/run-tests integration check_e2e_lunar_login_observer
```
