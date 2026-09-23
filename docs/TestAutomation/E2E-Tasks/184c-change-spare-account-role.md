# 184c — Change a spare approver role through shared account helpers

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

## Live VM acceptance

Read the spare Sam role, change administrator to standard once and verify the result and retained Jamie administrator. Protected/wrong-account/ambiguous requests must refuse before mutation. The complete consumer must observe request-selector eligibility/fallback through the app.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_change_spare_account_role
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **184c** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
