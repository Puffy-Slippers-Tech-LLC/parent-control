# 050a — Read a revocation warning and Cancel

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

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

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_revoke_cancel
```
