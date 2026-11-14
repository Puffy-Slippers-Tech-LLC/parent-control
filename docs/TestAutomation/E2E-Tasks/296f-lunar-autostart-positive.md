# 296f — Check allowed Lunar startup after sign-in

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP06 allowed Lunar startup after ordinary child sign-in** for
task **296b** and case 253.

Requires **296d** (owned public Lunar application/tray presence), **004**
(guarded normal sign-in), and **180** (public Parent allowance preparation).

Use the [supplied manual profile and autostart settings](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
after ordinary restore; report drift before setup changes.

## Implementation and acceptance

Set positive desktop time and allow Lunar through Parent. Sign Jordan in through
the shared normal entry. Independently observe the same account's owned Lunar
application/tray presence within the shared 180-second functional readiness
budget, proving the supplied autostart route actually starts the allowed app.
Quit normally and observe complete absence.

Use ordinary session readiness and the shared app-presence reader. The supplied
hidden autostart setting need not reveal a window. Do not test tray hide/restore,
Settings, vendor sign-in, game contents or gameplay. Do not build a new
continuous external-app observer or alter recorder/secret handling for this
slice. Existing watch, fresh credential-recipient, ownership, prompt,
complete-read and uncertain-input guards remain mandatory.

This qualifies a positive access control, not a continuous or zero-transient
window guarantee. Reboot enforcement belongs to the complete case.

Implement this planned selector in the existing E2E envelope before use; it is
not registered and needs no standalone system test:

```sh
tools/run-tests --vm onpc-Ubuntu26.04-110 e2e --subcategory e2e-heavy --qualify-lunar-autostart
```
