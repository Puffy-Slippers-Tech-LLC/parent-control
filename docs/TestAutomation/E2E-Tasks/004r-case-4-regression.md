# 004r — Requalify retained case 4

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Retained regression 4; no-child discovery**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001sb** — SEARCH05 administrator Parent launch and owned-window result.

## Read only this context

Read E2E-003's no-child branch and the retained [parent_discovery.py](../../../tests/e2e/parent_discovery.py) binding.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind the declared empty profile and complete public choice/window observations to the current adapters. Preserve empty-state meaning, ownership and incomplete-tree refusal.

## Live VM acceptance

Run exact case 4 in full, preserving every public result and fixture checkpoint. Require collection/cleanup and refresh coverage.

Run the complete registered case separately:

```sh
tools/run-tests e2e --id '4'
tools/generate_test_coverage.sh
```

Preserve its finite inputs, every recipe assertion, public results, capture
reconciliation and owned cleanup. Regenerate coverage after this successful
case; registration alone is not acceptance.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**004r** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
