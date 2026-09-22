# 035c — Launch and use a native fixture from the app grid

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03 native app-grid usable route**. Named consumer: task **035** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035p** — FIX04 native assets; LIFE04 fixture installation.
- **001t** — FILE01/02/06 terminal command, help/denial projections and normal close/return.
- **009** — UI16.

## Read only this context

Read only the delivered block rows and their named callables in the
[catalogue](../E2E-Building-Blocks.md), the selected consumer's recipe clauses,
and the affected safety/adapter tests. Follow the
[scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Use delivered prerequisite scopes; do not open predecessor briefs.

## Implementation

Reuse installed fixtures and qualified search. Bind grid activation, the owned app window and a declared normal input with independent effect.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

On the VM, launch the declared fixture from the grid, perform its normal action and independently observe the effect. Qualify separately supplied valid grid entry and wrong-target/uncertain-input refusal.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_native_grid_usable
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **035c**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
