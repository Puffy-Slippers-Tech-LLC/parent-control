# 296e — Open and close the Minecraft launcher

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/UI18 separate Minecraft launcher entry and exit** for
task **296a** and case 253. Requires **295**, the restored separate launcher
identity and normal command.

Use the [supplied manual profile](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
after ordinary restore; report drift before setup changes.

## Implementation and acceptance

As Jordan, invoke the declared system Flatpak desktop command and observe the
intended owner's signed-out launcher within the recipe's 180-second readiness
bound. That ready surface proves app access; no launcher-feature input is
required. Exit normally and independently observe complete absence. A fresh
observer must accept an independently supplied valid launcher.

Use the shared provider adapter and retain owner, ambiguity, prompt,
incomplete-read and uncertain-input guards. Do not sign in, inspect game
internals, open Settings or game menus, update/download anything, start Minecraft
through Lunar, invoke inner Java or exercise gameplay.

Implement this planned selector in the existing E2E envelope before use; it is
not registered and needs no standalone system test:

```sh
tools/run-tests --vm onpc-Ubuntu26.04-110 e2e --subcategory e2e-heavy --qualify-minecraft-entry-exit
```
