# 296e — Open and close the Minecraft launcher

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

Use the [supplied manual profile](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
in place. Report any launcher/profile setup gap before making setup changes.

## Scope and prerequisites

Deliver **APP01/02/UI18 separate Minecraft launcher entry and exit**.
Named consumer: task **296a** and case 253.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **295** — Restored separate Minecraft launcher identity and normal command.

## Implementation

Bind the normal Minecraft launcher's actual signed-out window, intended owner
and normal exit using the prepared FIX05 profile. A usable launcher surface is
the result. No vendor sign-in, download, game-menu or gameplay step is required;
do not start Minecraft through Lunar or invoke an inner Java executable.
Use the declared system Flatpak desktop command, independently of Lunar.
This provider binding has no registered callable or selector. Preserve owner,
ambiguity, complete-absence and uncertain-input guards in the shared adapter.

## Live VM acceptance

As Jordan, open the separate normal launcher to its usable signed-out surface
within the recipe's 180-second readiness bound. Exit through its normal control
and independently observe complete absence. An independently supplied valid
launcher entry works. Wrong owner or uncertain input refuses without replay.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_minecraft_entry_exit
```
