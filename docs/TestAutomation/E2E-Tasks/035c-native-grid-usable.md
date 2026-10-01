# 035c — Launch and use a native fixture from the app grid

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03 native app-grid usable route**. Named consumer: task **035** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035p** — native baseline assets and launchers; guarded read-only verification.
- **001t** — PARENT01 direct command, public management denial and desktop return.
- **009** — UI16.

## Implementation

Reuse installed fixtures and qualified search. Bind grid activation, the owned app window and a declared normal input with independent effect.

## Live VM acceptance

On the VM, launch the declared fixture from the grid, perform its normal action and independently observe the effect. Qualify separately supplied valid grid entry and wrong-target/uncertain-input refusal.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_native_grid_usable
```
