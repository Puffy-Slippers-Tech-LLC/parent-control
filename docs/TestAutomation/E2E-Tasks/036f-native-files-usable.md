# 036f — Launch separate usable native windows from Files

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03 native file-manager usable/new-window route**. Named consumer: task **036a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **047** — APP04 and FLOW08 native usable-app observations.

## Implementation

Verify the native baseline assets already supplied through 047. Open Files
directly at that prepared fixture directory through FILE04, then bind
only the exact fixture's activation and supported separate-window action. Reuse
the existing location adapter if needed; no folder browsing, copy operation,
Properties dialog or view customization belongs to this launch check. Reuse
owned app observations and one normal usability input.

## Live VM acceptance

Launch from Files, observe a normal action's effect, then open a distinguishable second window beside the first. Independently compare the original activity; wrong file or a reused first window refuses.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_native_files_usable
```
