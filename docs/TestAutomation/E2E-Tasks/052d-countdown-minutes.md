# 052d — Measure the displayed countdown's minute ticks

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **TIME02 minute-precision sampling**. Named consumer: task **052a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052** — TIME01 child-desktop presence and limits-off absence.
- **051** — FLOW13 daily-only, fresh/same Parent entry with observed G=0.
- **052c** — TIME03.

## Implementation

Compose countdown snapshots with guarded waits and monotonic elapsed comparisons for the minute-format branch only. Bind precision and tolerance before input.

## Live VM acceptance

Publicly prepare short daily-only time, enter the child and observe successive minute samples over real intervals. Qualify independently supplied child entry and refuse reversed, stale or wrong-owner samples.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_countdown_minutes
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
