# 048f — Observe overlay password rejection and Cancel

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **AUTH02 overlay rejection/Cancel and preserved-form readback**. Named consumer: task **048b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **021** — FLOW05/06/07 kiosk.
- **048c** — Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result.
- **048d** — AUTH02 overlay approval; REQUEST11/12 success and automatic child return.

## Implementation

Reuse Shell recipient and sealed input from 048c/048d. Bind explicit wrong-password rejection, normal Cancel and the same usable overlay choices.

## Live VM acceptance

In separate fresh attempts, submit one declared wrong password and observe rejection before Cancel; Cancel another fresh prompt without a secret. Compare preserved choices and require sealed capture/cleanup.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_overlay_rejection
```
