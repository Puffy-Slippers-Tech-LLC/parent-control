# 002r — Requalify retained case 6

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Retained regression 6; full terminal management denial**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001t** — FILE01/02/06 terminal command, help/denial projections and normal close/return.

## Read only this context

Read E2E-004's terminal branch and [parent_terminal.py](../../../tests/e2e/parent_terminal.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind the complete retained customer recipe to the qualified terminal, public denial and return operations. Preserve the ready executable registration and all assertions.

## Live VM acceptance

Run exact case 6; require explicit management denial, normal closure/return, collection, cleanup and coverage refresh. Launcher absence or echoed command text cannot satisfy it.

Run the complete registered case separately:

```sh
tools/run-tests e2e --id '6'
tools/generate_test_coverage.sh
```

Preserve its finite inputs, every recipe assertion, public results, capture
reconciliation and owned cleanup. Regenerate coverage after this successful
case; registration alone is not acceptance.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**002r** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
