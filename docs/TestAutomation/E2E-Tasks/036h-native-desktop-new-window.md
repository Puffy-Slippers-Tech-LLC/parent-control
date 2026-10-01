# 036h — Open a second native window from the desktop

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02 desktop separate-window route**. Named consumer: task **036b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036g** — APP01/02/03 DING desktop entry and usable launch.

## Implementation

Extend the qualified desktop adapter with the supported normal new-window gesture for an existing S activity. Keep old and new public window identities distinct.

## Live VM acceptance

Capture S activity, use the desktop entry to open a distinguishable second window, and independently prove the original activity remains. Presenting the first window or substituting another launch route fails.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_native_desktop_new_window
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
