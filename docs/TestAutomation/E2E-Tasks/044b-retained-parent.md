# 044b — Return to an existing Parent desktop and window

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **DESK09 and FLOW01 retained Parent entry**. Named consumer: task **044** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043a** — GDM02 retained-child lock entry; DESK08/11.
- **044a** — DESK10 same-desktop window switching.

## Implementation

Reuse qualified Switch User, recipient proofs and DESK10 to return to an existing Parent window. Keep current child/page and immutable settings explicit; navigate to Screen Limits before its settings read.

## Live VM acceptance

Leave a recognizable Parent window, switch away and legitimately return, foreground that same window and compare public state before editing. Independently supplied retained entry works; absent windows refuse without relaunch.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_retained_parent
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
