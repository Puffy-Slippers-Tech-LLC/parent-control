# 296 — Observe Lunar command denial

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02 original-AppImage policy denial and complete public absence**
for task **296b** and [case 253](../E2E-Scenario-Recipes.md#e2e-052).

Requires **296c** (normal original-AppImage launch/Quit and owned absence) and
**079** (public saved match/access editing).
Use the [supplied manual profile](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
after ordinary restore; report drift before setup changes.

## Implementation and acceptance

Save the declared Lunar policy through Parent. As Jordan with usable desktop
time, invoke the same original AppImage once and require a specific public policy
denial plus complete Lunar application/tray absence. An unrelated allowed app
must remain usable. A hidden launcher, generic launch failure, process list or
rule file cannot supply the denial result.

Reuse the delivered allowed launch/Quit binding; run an affected allowed control
only when the shared route changes. Preserve ownership, complete-read, prompt
and uncertain-input guards. No Settings, tray hide/restore, vendor accounts,
downloads, game launch, game internals or gameplay checks.

Implement this planned selector in the existing E2E envelope before use; it is
not registered and needs no standalone system test:

```sh
tools/run-tests --vm onpc-Ubuntu26.04-110 e2e --subcategory e2e-heavy --qualify-lunar-denial
```

Use affected shared safety checks and owned cleanup. This slice does not pass
case 253 or qualify sign-in/reboot persistence.
