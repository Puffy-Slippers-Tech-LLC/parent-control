# 296a — Check Minecraft launcher access after approval

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

Use the [supplied manual profile](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
in place. Report any launcher/profile setup gap before making setup changes.

## Session boundary

Bind the separate normal Minecraft launcher, its usable signed-out surface,
normal exit and specific public policy denial. Reuse the launcher owner/exit
mechanics from 296e. Vendor sign-in, downloads and game launch are outside scope.

Reuse the delivered scope of tasks **296e** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 and UI18 separate normal Minecraft launcher launch/denial binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296e** — APP01/02/UI18 separate signed-out Minecraft launcher entry and exit.
- **079** — Public saved match/access editing for the declared Minecraft launcher target.

## Implementation

Use the already restored FIX05 profile's separately declared normal Minecraft
launcher and policy target. Reuse 296e's intended launcher owner/window,
usable signed-out surface and normal-exit observations independently of Lunar.
Qualify the real launch command and specific policy denial with complete public
launcher absence. A running process alone cannot pass.
Apply the approved provider exception
only inside explicit external adapters; no embedded Java launch, download, sign-in
fallback or generic title/coordinate targeting.

## Live VM acceptance

As Jordan, open the prepared Minecraft launcher through its separate normal route
and observe its usable signed-out surface within the recipe's 180-second readiness bound.
Exit normally and independently observe absence. With its declared target Soft
Blocked and no soft-app permission, invoke that same route once and require a
specific public policy denial and complete launcher absence. Real parent approval
including soft apps must restore the same usable launcher. Keep desktop
time positive and an unrelated allowed app usable. Reject wrong owner,
ambiguity, unavailable launcher inputs and uncertain input; never replay.

Reuse unchanged separate Minecraft launcher entry/exit qualification;
this slice qualifies that launcher's launch/denial and its changed
safety boundaries. Apply the test scope mandate: use affected product operations
and existing shared safety checks, without new tests mirroring this adapter.
Live operations retain every guard.
The following focused qualification route is planned; implement it in the
existing guarded envelope before invocation, without a standalone system
registration for this E2E building block:

```sh
tools/run-tests system check_e2e_minecraft_provider
```
