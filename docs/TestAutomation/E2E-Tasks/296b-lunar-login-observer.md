# 296b — Check blocked Lunar access after sign-in

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/06 blocked Lunar access after ordinary child sign-in** for
case 253.

Requires **296f** (working allowed autostart control) and **296**
(same original-AppImage command's specific public denial).

Use the [supplied manual profile and autostart settings](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
after ordinary restore; report drift before setup changes.

## Implementation and acceptance

Save Lunar's declared Soft Blocked policy with desktop time available and no
soft-app permission. Sign Jordan in through the shared normal entry.
Require complete public Lunar application/tray absence. Invoke the same original
AppImage command once and require specific public policy denial, then
independently observe complete absence again. An unrelated allowed app must
remain usable. A missing tray alone or generic startup failure cannot pass.

Reuse the allowed-startup qualification, normal session readiness, same-route
denial and complete public app reader. The result is blocked app access after
sign-in, not a game-specific continuous interval or zero-transient-window claim.
Do not introduce a new observer/recorder lifecycle, a 90-second sampling matrix,
tray hide/restore, Settings, game internals, accounts, downloads or gameplay.

Preserve shared watch, credential-recipient, ownership, ambiguity, prompt,
incomplete-read and uncertain-input guards. Run affected shared safety checks;
unchanged recorder/secret infrastructure needs no renewed qualification.

Implement this planned selector in the existing E2E envelope before use; it is
not registered and needs no standalone system test:

```sh
tools/run-tests --vm onpc-Ubuntu26.04-110 e2e --subcategory e2e-heavy --qualify-lunar-login-denial
```
