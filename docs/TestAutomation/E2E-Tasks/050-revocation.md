# 050 — Cancel and confirm grant revocation

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **PARENT17, PARENT18**. First scheduled consumer: [E2E-008, case 22](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement the warning/target observation, then explicit Cancel/Confirm, closure, saved-state and settings observations. A grant is obtained through kiosk approval; no grant state is seeded internally.

## Live VM acceptance

On the VM with a real grant, Cancel preserves displayed settings/balance within elapsed-time bounds. Reopen, Confirm, and independently read the new daily/one-time explanation. Child effects remain separate later observations.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_revocation
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
