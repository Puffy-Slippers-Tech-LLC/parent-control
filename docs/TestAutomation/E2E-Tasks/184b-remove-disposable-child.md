# 184b — Remove a logged-out spare child through shared account helpers

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **ACCOUNT02 remove-child**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **184** — ACCOUNT01/02 shared account read/create; AUTH04 protected-account guards.

## Read only this context

Read ACCOUNT02 and the maintained shared account/cleanup helpers delivered by task 184.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Remove only the explicitly registered, logged-out spare child through the shared command/API route. Reject active accounts, baseline accounts, the station and the last administrator before any mutation. No Users dialog or confirmation-cancel exercise.

## Live VM acceptance

Prepare the spare in this attempt, remove it once and independently require only that account absent. Prove protected-account and wrong-owner refusals leave the account set unchanged. Parent/request refresh and fallback remain the complete scenario's GUI assertions.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_remove_disposable_child
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **184b** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
