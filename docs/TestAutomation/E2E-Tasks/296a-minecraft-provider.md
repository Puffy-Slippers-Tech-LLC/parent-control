# 296a — Play the prepared Minecraft local world

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the fixed local-world selection, normal play action and independent visible effect. Reuse 296e's game entry/exit; unavailable world/assets remain a blocker.

Reuse the delivered scope of tasks **296e** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 and UI18 Minecraft local-world binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296e** — APP01/02/UI18 Lunar-to-Minecraft entry and return.

## Implementation

Use the already restored FIX05 profile and qualified Lunar launch surface.
Reuse 296e's real game-launch/normal-exit operations and intended Minecraft
owner/window binding. Add one fixed local-world action and its independent
visible effect, then independently observe return to the same Lunar surface.
Apply the approved provider exception
only inside explicit external adapters; no inner Java launch, download, sign-in
fallback or generic title/coordinate targeting.

## Live VM acceptance

From independently supplied valid Lunar entry, launch the prepared Minecraft
world and observe the declared action/result within the recipe's 180-second game
readiness bound. Exit normally and independently observe Lunar. Reject wrong
world/owner, ambiguity, unavailable assets and uncertain input; never replay.

Reuse unchanged Lunar launch/Quit and Minecraft menu/exit qualification; this
slice qualifies only the local-world action/result and its changed safety
boundaries. Focused adapter checks cover wrong-world/owner, ambiguous targets,
unavailable assets and uncertain input; live operations retain every guard.
The following fixed qualification is planned; implement and register it before
invocation:

```sh
tools/run-tests integration check_e2e_minecraft_provider
```
