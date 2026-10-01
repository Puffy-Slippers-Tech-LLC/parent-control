# 043b — Qualify a fresh child login with usable daily time

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **GDM06/07 and FLOW15 fresh-child success**. Named consumer: task **043** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **041** — PARENT09, FLOW02.

## Implementation

Bind the intended child's fresh GDM recipient and success using two fresh proofs and sealed single-use input. Reuse the existing account/desktop adapters.

## Live VM acceptance

Prepare positive daily time through Parent and observe saving, Switch User, log the child in correctly and independently observe the usable child desktop. Wrong-recipient and stale-proof tests must pass.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_fresh_child_allowed
```
