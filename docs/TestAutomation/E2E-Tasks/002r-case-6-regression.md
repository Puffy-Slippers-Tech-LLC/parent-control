# 002r — Requalify retained case 6

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Retained regression 6; shared PARENT01 direct-command management denial**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001t** — PARENT01 direct command, public management denial and desktop return.
  its historical `terminal` selector does not require opening a terminal.

## Read only this context

Read E2E-004's case 6 branch, PARENT01 and [parent_terminal.py](../../../tests/e2e/parent_terminal.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Reuse `onpc_parent::launch` with the denial expectation, exactly as ordinary
Parent cases reuse it with the management-window expectation. Invoke the fixed
command directly as the active desktop user; no terminal or app search.
Preserve the ready executable registration, specific public denial, management
absence and independently observed desktop return.

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
