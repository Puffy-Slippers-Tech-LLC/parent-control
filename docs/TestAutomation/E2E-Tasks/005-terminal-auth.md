# 005 — Qualify the shared package command boundary

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **AUTH03 administrator command authority; FILE06 package output**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **005a** — Product-free graphical start and verified package staging.

## Read only this context

Read AUTH03, FILE01/02/06, LIFE04 and the existing guarded command/artifact validation in `installed_setup` and `vm_transport`.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Bind one fixed package-operation command to the owned VM, verified release input and authorized administrator context. Validate arguments and artifacts before submission. Carry completion and the actual package notice as bounded stdout/stderr; do not create a Terminal or exercise an unrelated sudo password prompt.

## Live VM acceptance

Qualify independent valid command input and reject unregistered commands, wrong artifacts, wrong VM/attempt and replay. A real package command's completion/notice must be read independently under the existing attempt envelope; installation composition remains task 006.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_package_authority
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **005** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
