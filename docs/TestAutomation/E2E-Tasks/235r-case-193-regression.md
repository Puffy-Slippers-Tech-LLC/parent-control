# 235r — Requalify retained case 193

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Retained regression 193; both installed commands/manuals and clear desktop return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001t** — PARENT01 direct command, public management denial and desktop return.

## Read only this context

Read E2E-042's command-help branch, its two fixed commands/manuals, INFO02 and the case 193 executable binding in the inventory.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Keep both registered help/manual results from guarded SSH stdout and the clear desktop return. Use bounded meaningful public content; product absence remains required.

## Live VM acceptance

Run exact case 193 in full, read both required outputs, collect evidence, clean up and refresh coverage.

Run the complete registered case separately:

```sh
tools/run-tests e2e --id '193'
tools/generate_test_coverage.sh
```

Preserve its finite inputs, every recipe assertion, public results, capture
reconciliation and owned cleanup. Regenerate coverage after this successful
case; registration alone is not acceptance.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**235r** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
