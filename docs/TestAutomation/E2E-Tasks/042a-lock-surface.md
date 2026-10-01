# 042a — Lock a desktop and observe its challenge surface

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **DESK05/06 explicit Lock, curtain and challenge reveal**. Named consumer: task **042** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 direct logout command and independent GDM result.

## Implementation

Reuse the shared DESK05 lock command or Super+L shortcut. The Shell lock adapter observes the resulting surface and supplies a bounded normal-key reveal only when the challenge is hidden by its curtain. Observe lock ownership and that ordinary desktop input is unavailable; do not authorize a secret or navigate Shell menus.

## Live VM acceptance

Lock an observed usable fixture desktop, independently identify the lock surface, reveal the challenge and observe its public identity. Qualify an independently supplied lock and reject wrong session/ambiguous surfaces.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_lock_surface
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
