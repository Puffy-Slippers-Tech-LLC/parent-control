# 296e — Launch Minecraft to its menu and exit normally

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/UI18 Lunar-to-Minecraft entry and return**. Named consumer: task **296a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296** — APP06 snapshot and APP01/02/03/UI18 Lunar launch, tray and Quit bindings.

## Implementation

Bind Lunar's actual game-launch action, intended Minecraft owner and normal game exit using only the already prepared profile. No download, sign-in fallback or inner Java launch.

## Live VM acceptance

From an independently supplied Lunar surface, launch the prepared game to its public menu within the existing 180-second readiness bound. Exit normally and independently observe the same Lunar entry. Wrong owner or uncertain input refuses.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_minecraft_entry_exit
```
