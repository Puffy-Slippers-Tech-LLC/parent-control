# 184b — Remove a logged-out spare child through shared account helpers

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

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

Prepare the spare in this attempt, remove it once and independently require only
that account absent. Focused harness checks prove protected-account and
wrong-owner refusals before transport/discovery, leaving the account set
unchanged; the live route keeps the same guards. Parent/request refresh and
fallback remain the complete scenario's GUI assertions.

Cases 180/181 also need independently prepared profiles containing exactly two
eligible registered spare children, or only the one to be removed, respectively.
The current helper's empty-account
preparation removes fixture children and is not this protected spare-removal
binding. Plan and qualify these disposable-child profiles before their consumers;
do not relax baseline-account protection or remove ordinary household accounts.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_remove_disposable_child
```
