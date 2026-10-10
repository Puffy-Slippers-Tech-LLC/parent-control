# 116b — Launch and use Flatpak fixtures by command

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Flatpak command usable/new-window route**. Named consumer: task **116** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **116p** — Flatpak baseline assets and FIX06 verification.
- **047** — APP04 and FLOW08 native usable-app observations.

## Implementation

Reuse the qualified installed Flatpak profile and guarded SSH command binding. Bind fixed command launch, owned window/usability observations, immutable activity and a supported separate-window command.

## Live VM acceptance

Launch each declared Flatpak fixture, perform its normal action, capture S and open a distinguishable second instance while the earlier activity remains. Qualify independent guarded SSH command entry and wrong-scope/echo-only/uncertain-input refusal.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_flatpak_command_usable
```
