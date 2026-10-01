# 035c — Launch and use a native fixture from the app grid

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03 native app-grid usable route**. Named consumer: task **035** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035p** — FIX04 native assets; LIFE04 fixture installation.
- **001t** — PARENT01 direct command, public management denial and desktop return.
- **009** — UI16.

## Implementation

Reuse installed fixtures and qualified search. Bind grid activation, the owned app window and a declared normal input with independent effect.

## Live VM acceptance

On the VM, launch the declared fixture from the grid, perform its normal action and independently observe the effect. Qualify separately supplied valid grid entry and wrong-target/uncertain-input refusal.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_native_grid_usable
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
