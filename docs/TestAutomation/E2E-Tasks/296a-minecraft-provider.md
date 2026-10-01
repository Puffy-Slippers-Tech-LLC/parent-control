# 296a — Play the prepared Minecraft local world

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add the fixed local-world selection, normal play action and independent visible effect. Reuse 296e's game entry/exit; unavailable world/assets remain a blocker.

Reuse the delivered scope of tasks **296e** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 and UI18 Minecraft local-world binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296** — APP06 snapshot and APP01/02/03/UI18 Lunar launch, tray and Quit bindings.
- **296e** — APP01/02/UI18 Lunar-to-Minecraft entry and return.

## Implementation

Use the already restored FIX05 profile and qualified Lunar launch surface.
Bind Lunar's real game-launch action, the intended Minecraft owner/window, one
fixed local-world action and its independent visible effect. Qualify normal game
exit and return to the same Lunar surface. Apply the approved provider exception
only inside explicit external adapters; no inner Java launch, download, sign-in
fallback or generic title/coordinate targeting.

## Live VM acceptance

From independently supplied valid Lunar entry, launch the prepared Minecraft
world and observe the declared action/result within the recipe's 180-second game
readiness bound. Exit normally and independently observe Lunar. Reject wrong
world/owner, ambiguity, unavailable assets and uncertain input; never replay.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_minecraft_provider
```
