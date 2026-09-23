# 193 — Change connectivity through shared system commands

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **LIFE06**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 direct logout command and independent GDM result.
- **010** — UI17 Parent Screen time limit binding; installed qualification and owned cleanup passed.
- **044a** — DESK10 same-desktop window switching.

## Read only this context

Read LIFE06, the owned VM network configuration and shared guarded command transport and cleanup contracts.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Use a fixed NetworkManager/nmcli operation for the declared guest test connection. Preserve the independent management/SSH and observation route; validate interface/connection ownership before changes. Record real offline/online state with public system readback. Do not navigate Quick Settings or inject product transport faults.

## Live VM acceptance

Disconnect the declared test connection, independently confirm the real offline condition, observe the existing Parent window remains usable, then reconnect and independently confirm recovery. Refuse wrong interface/connection and uncertain replay. If the VM has no independent management path, report that concrete prerequisite instead of disconnecting the harness.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_operate_public_connectivity_controls
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **193** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
