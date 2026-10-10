# 296c — Launch Lunar and Quit through its normal controls

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03/UI18 Lunar original-AppImage usable launch and Quit**. Named consumer: task **296** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **295** — FIX05; restored Lunar/AppImageLauncher/autostart/Minecraft prerequisites only. Blocker: profile and repeatable setup unqualified; resume when the manual assets and standard restore path are available.
- **052c** — TIME03.

## Implementation

Use the restored FIX05 profile and explicit external adapter to bind the original AppImage command, actual Lunar window and genuine Quit. Preserve owner, ambiguity and uncertain-input guards.

No Lunar callable or selector is registered. `AccessibleUI.native_launch_command`
is fixed to the repository native fixture and cannot launch this AppImage by
changing case data. Extend the shared external-app command/observation adapter
with the exact FIX05 original path; keep normal Lunar Quit and complete absence
separate from a close-to-tray action. Native grid/denial/closure qualification is
not a prerequisite for this allowed Lunar binding.

## Live VM acceptance

Launch the prepared original AppImage, independently observe usable Lunar, Quit normally and prove absence within the complete surrounding desktop. Independently supplied valid Lunar entry works; process/rule probes cannot pass.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_lunar_launch_quit
```
