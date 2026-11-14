# 296a — Check Minecraft launcher access after approval

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/UI18 separate Minecraft launcher allow/deny/approval binding**
for case 253.

Requires **296e** (separate signed-out launcher entry/exit) and **079**
(public saved match/access editing). Use the
[supplied manual profile](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
after ordinary restore; report drift before setup changes.

## Implementation and acceptance

Reuse the separate normal launcher and its declared policy target, independently
of Lunar. With desktop time positive and an unrelated allowed app usable:

- Observe the allowed signed-out launcher through its normal command, then exit.
- Save Soft Blocked with no soft-app permission. Invoke that same command once;
  require specific public policy denial and complete launcher absence.
- Obtain real parent approval including soft apps. Require the same launcher
  to become available again, then exit normally and observe absence.

The ready signed-out surface proves access. Do not add a settings, account,
launcher-function, download, game-menu, inner-Java or gameplay exercise. Preserve
owner, prompt, complete-read, ambiguity and uncertain-input guards; never replay
an uncertain action or substitute a launch route.

Reuse unchanged entry/exit qualification and existing shared safety checks.
Implement this planned selector in the existing E2E envelope before use; it is
not registered and needs no standalone system test:

```sh
tools/run-tests --vm onpc-Ubuntu26.04-110 e2e --subcategory e2e-heavy --qualify-minecraft-access
```
