# 065a — Prepare grant-only time and explicit revoke-first entry

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW13 grant-only profile and explicit revoke preparation**. Named consumer: task **065** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **051** — FLOW13 daily-only, fresh/same Parent entry with observed G=0.
- **050** — PARENT17, PARENT18.

## Implementation

Compose real kiosk approval at daily=0 with retained Parent readback and final GDM return. Require explicit revoke-first input when clearing an existing grant.

## Live VM acceptance

Observe D=0/G>0 after real approval and finish at GDM. In a separate attempt, explicitly revoke first and independently read G=0 before preparing the grant; an unexpected undeclared existing grant refuses.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_grant_only_profile
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
