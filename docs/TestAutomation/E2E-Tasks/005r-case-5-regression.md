# 005r — Requalify retained case 5

Estimate: 30–50 minutes; an estimate, never a stop timer. Follow the
[master execution contract](../E2E-Execution-Plan.md#execute-one-task) and its
[provider rules](../E2E-Execution-Plan.md#external-provider-work-within-the-sequence).
This brief does not select or skip tasks.

## Scope and prerequisites

Deliver **Retained regression 5; standard-account app-grid unavailability**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.

## Read only this context

Read E2E-004's app-grid branch and the retained [parent_access.py](../../../tests/e2e/parent_access.py) binding.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Preserve the recipe's declared discovery/profile setup, exact query and stable absence comparison. Launcher unavailability is separate from terminal execution denial.

## Live VM acceptance

Run exact case 5 with every existing public result, collection and cleanup. Refresh coverage; no partial search slice substitutes for this case.

Run the complete registered case separately:

```sh
tools/run-tests e2e --id '5'
tools/generate_test_coverage.sh
```

Preserve its finite inputs, every recipe assertion, public results, capture
reconciliation and owned cleanup. Regenerate coverage after this successful
case; registration alone is not acceptance.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**005r** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
