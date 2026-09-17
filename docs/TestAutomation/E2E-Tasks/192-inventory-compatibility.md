# 192 — Align inventory regression fixtures with the current metadata

Estimate: 25–45 minutes. Follow the
[master](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read the inventory declaration schema and named regression fixtures. Obtain
counts with a narrow JSON projection; read only recipe clauses referenced by
those assertions. No other task brief or full customer catalogue is required.

## Scope and implementation

Repair only [inventory regression fixtures/assertions](../../../tests/unit/test_e2e_inventory.py)
for the current [inventory](../../../tests/e2e/scenarios.json) and
[recipe contract](../E2E-Scenario-Recipes.md). Use existing source and collectors;
no capability or previous task is required.

Reconcile counts with 252 cases, five ready bindings and 247 pending bindings.
Fix fixtures that unconditionally remove already-absent backend evidence or
omit referenced contract files. Customer acceptance uses readable notice content
without a color gate, and E2E-033 is a public connectivity/retry journey.
Preserve matrix closure, stable IDs, exact notice text, ready selection,
missing-file refusal, forbidden backend evidence and separate fault owners.
Do not change product behavior checks merely to fit the implementation.

## Acceptance

This metadata-only prerequisite is the master's explicit host-only exception;
a VM run would not validate its parser/fixture changes. Run:

```sh
tools/run-unit-tests 'tests/unit/test_e2e_inventory.py' -q
tools/generate_test_coverage.sh
```

The launcher runs `tools/generate_test_coverage.py`; require both commands to
succeed. Missing collection prerequisites remain a current blocker, not grounds
for hand-editing generated counts or using another checkout's interpreter.

## Close out

Reconcile the current inventory totals in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and
[E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
Keep all block/scenario readiness unchanged: this earns no live acceptance.
Check task 192 in the [master's queue](../E2E-Task-Queue.md), refresh the
master's **Next task** pointer, remove any resolved blocker, and delete this brief when its context is in maintained source/contracts.
Replace its queue link with plain text and validate changed Markdown through
`tools/read-only links`. No new evidence document or accumulated history.
