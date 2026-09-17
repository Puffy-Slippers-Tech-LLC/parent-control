# 038 — Add, inspect, preview and remove attachments

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FEED06, FEED07, FEED12, FEED13**. First scheduled consumer: [E2E-031, case 152](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **037** — FILE03 open/cancel.
- **010** — UI17.
- **031** — FEED09 validation/control snapshots.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Extend FIX04 with bounded synthetic files. Implement add/list result, one item's name/size/order, optional offered preview, and removal with exact remaining list. No private storage reads; unoffered preview is explicitly inapplicable.

## Live VM acceptance

On the installed VM, add multiple synthetic files, read their names/sizes, preview only if offered, remove one and compare the remaining list. Qualify count and per-file rejection. Exclude diagnostics through the public toggle and qualify the declared 8 MiB aggregate boundary. The complete filename, mixed-selection and original-file-change matrix belongs to case 154; private draft bytes are never inspected.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_attachments
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
