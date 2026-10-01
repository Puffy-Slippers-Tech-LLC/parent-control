# 044b — Return to an existing Parent desktop and window

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

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

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_retained_parent
```
