# 050 — Confirm grant revocation and read balances

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add Confirm, warning closure and independent saved time readback. Reuse 050a's warning/target and Cancel; child effects remain later consumers.

Tasks **050a** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **PARENT17, PARENT18**. First scheduled consumer: [E2E-008, case 22](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **050a** — PARENT17/18 revocation target, warning and Cancel.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement the warning/target observation, then explicit Cancel/Confirm, closure, saved-state and settings observations. A grant is obtained through kiosk approval; no grant state is seeded internally.

## Live VM acceptance

On the VM with a real grant, Cancel preserves displayed settings/balance within elapsed-time bounds. Reopen, Confirm, and independently read the new daily/one-time explanation. Child effects remain separate later observations.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_revocation
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
