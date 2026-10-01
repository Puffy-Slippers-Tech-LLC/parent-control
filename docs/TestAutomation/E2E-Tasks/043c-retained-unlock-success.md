# 043c — Unlock the intended retained child successfully

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **GDM02 retained lock entry and DESK08 successful unlock**. Named consumer: task **043a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.
- **042** — DESK05, DESK06, DESK07.

## Implementation

Bind retained-child GDM selection to its lock destination. Compose two fresh lock proofs, sealed single-use input and successful return to the original desktop.

## Live VM acceptance

Capture child activity with positive daily time, lock normally and unlock correctly. Independently compare the same usable activity. Qualify separate valid retained-lock entry and refuse GDM proofs or wrong recipients.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_retained_unlock_success
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
