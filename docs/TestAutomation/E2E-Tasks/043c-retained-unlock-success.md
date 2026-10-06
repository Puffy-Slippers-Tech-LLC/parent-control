# 043c — Unlock the intended retained child successfully

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

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

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_retained_unlock_success
```
