# 050a — Read a revocation warning and Cancel

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **PARENT17/18 revocation target, warning and Cancel**. Named consumer: task **050** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

## Implementation

Obtain a real kiosk grant, open the owned revocation warning, verify target and use Cancel. Reuse public settings/time observers; never seed grant state.

## Live VM acceptance

With a real grant, capture public settings/balance, open and Cancel the warning and independently compare unchanged values within elapsed-time bounds. Wrong child/confirmation refuses.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_revoke_cancel
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
