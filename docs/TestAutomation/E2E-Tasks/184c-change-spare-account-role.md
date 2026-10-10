# 184c — Change a spare approver role through shared account helpers

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **ACCOUNT02 change-role**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **184** — ACCOUNT01/02 shared account read/create; AUTH04 protected-account guards.

## Read only this context

Read ACCOUNT01/02, AUTH04 and the maintained spare-account helper and protection tests.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Change only the registered spare approver's role using the shared supported system-command/API route. Retain the active Jamie administrator and independently read the resulting role. No Users selector or Unlock prompt.

Source gap: task 184's standard-child creation does not prepare a spare
administrator. Add the finite registered Sam-approver preparation to the shared
account fixture before qualification, including independent role readback and
owned cleanup. Refuse borrowing the active/last administrator or changing a
baseline account. If that preparation cannot fit this slice, extract it ahead
of this task; do not silently assume Sam already exists after restore.

## Live VM acceptance

Read the spare Sam role, change administrator to standard once and verify the result and retained Jamie administrator. Protected/wrong-account/ambiguous requests must refuse before mutation. The complete consumer must observe request-selector eligibility/fallback through the app.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_change_spare_account_role
```
