# 036h — Open a second native window from the desktop

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02 desktop separate-window route**. Named consumer: task **036b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036g** — APP01/02/03 DING desktop entry and usable launch.

## Implementation

Extend the qualified desktop adapter with the supported normal new-window gesture for an existing S activity. Keep old and new public window identities distinct.

Bind the fixture's declared `--instance secondary` route and extend the shared
APP02/04 reader for that public endpoint. `gui_application.py::main` accepts the
instance, while the installed native launch/projection currently accepts only
primary. A supported DING new-window activation remains unqualified; record
that route before use, without recreating a native double-click task. Reuse
036g's unchanged placement/first-launch evidence.

## Live VM acceptance

Capture S activity, use the desktop entry to open a distinguishable second window, and independently prove the original activity remains. Presenting the first window or substituting another launch route fails.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_native_desktop_new_window
```
