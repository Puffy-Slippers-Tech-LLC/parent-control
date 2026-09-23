# 036 — Prepare synthetic files through shared commands

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FILE05 bounded copy/rename; FIX04 synthetic files**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **009** — UI16.

## Read only this context

Read FIX04 and FILE05 in the catalogue, the prepared synthetic attachment inputs, and the existing fixture transfer/ownership helpers.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Implement fixed shared SSH file operations for the declared synthetic fixtures: stage, bounded listing/read, copy and rename. Use argument arrays and canonical owned fixture directories. Reject traversal, symlinks, wrong owner, duplicate destinations and unregistered files before mutation. Reuse one helper; no Nautilus location/copy/rename tour.

## Live VM acceptance

Stage the finite fixtures including names with spaces, copy and rename declared files, and independently verify the exact resulting files/content. Failed validation leaves the fixture unchanged. Uncertain operations refuse replay. Qualify cleanup of only owned files. Chooser GUI and file-manager enforcement launch routes remain their own product consumers.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_files
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **036** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
