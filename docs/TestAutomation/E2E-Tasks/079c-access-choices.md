# 079c — Save one app's public access choice

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **PARENT16 Allowed/Hard/Soft save and row readback**. Named consumer: task **079** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **078** — PARENT13/15 ordinary Save/Cancel/Reset and local invalid drafts.

## Implementation

Bind UI15 for one native app's access choice and compose it with existing save observations and row identity. Do not implement enforcement observations here.

## Live VM acceptance

Save Allowed, Hard Blocked and Soft Blocked in order and independently read each saved choice. Repeat from an independently supplied App Limits entry; wrong row or disabled control refuses.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_access_choices
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
