# 079d — Observe native launch denial without a prior window

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP02 and FLOW08 native grid/command blocked-launch results**. Named consumer: task **079a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **047** — APP04; FLOW08 native usable-app scope.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

## Implementation

Bind usable, hidden-grid and explicit command-denial observations under publicly saved Allowed/Hard/Soft choices. A hidden grid result requires its separately declared command-denial witness.

## Live VM acceptance

In fresh VM attempts with no earlier target window, save each declared access choice and observe native grid/command results, including an unaffected allowed target. Qualify independent valid entry; incomplete absence cannot pass.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_native_denial
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
