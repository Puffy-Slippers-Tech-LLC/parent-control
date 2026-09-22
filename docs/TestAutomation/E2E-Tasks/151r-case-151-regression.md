# 151r — Requalify retained case 151

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Retained regression 151; complete About/license recipe and migration regression close-out**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **185l** — ABOUT02/03 actual license handler identity/content and close/return.

## Read only this context

Read E2E-030, case 151's inventory binding and [parent_about.py](../../../tests/e2e/parent_about.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind its complete About/license/return sequence to the qualified viewer and owned controls. Before ending the initial migration, audit the existing results for cases 1, 3, 4, 5, 6 and 193 against any intervening shared changes and rerun the affected cases. This is the master's shared regression gate, not a dependency on another scenario's execution.

## Live VM acceptance

Run exact case 151 with all existing public results, collection and cleanup, then refresh coverage. Close the shared migration gate only with valid full results for all seven retained cases.

Run the complete registered case separately:

```sh
tools/run-tests e2e --id '151'
tools/generate_test_coverage.sh
```

Preserve its finite inputs, every recipe assertion, public results, capture
reconciliation and owned cleanup. Regenerate coverage after this successful
case; registration alone is not acceptance.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**151r** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
