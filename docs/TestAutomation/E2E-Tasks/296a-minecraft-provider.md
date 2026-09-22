# 296a — Qualify Minecraft launch, local play and exit

Estimate: 40–60 minutes of focused implementation and validation; not a stop
timer. Follow the [master execution contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **APP01/02/03 and UI18 Minecraft local-world binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296** — APP06 snapshot and APP01/02/03/UI18 Lunar launch, tray and Quit bindings.

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
isolation first. Use the shared watchvm observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_minecraft_provider
```

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the callable and exact qualified scope in the
[catalogue](../E2E-Building-Blocks.md), check **296a** only after acceptance and
cleanup, advance to the following unchecked row, and delete this brief after
enduring context is maintained. The complete scenario stays in its own task.
