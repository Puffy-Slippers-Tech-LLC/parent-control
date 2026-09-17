# 109a — Qualify Snap app-grid launches

Estimate: 25–45 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Snap app-grid route**. First scheduled consumer: [E2E-019, case 86](../E2E-Scenario-Recipes.md#e2e-019).
Read the [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **109** — FIX04 Snap assets; APP01/02/03/04 and FLOW08 command route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the staged Snap fixtures and qualified command/result/activity readers. Bind SEARCH operations to the actual grid entries and compose the grid launch. Require a separately identified new window when one is already open; record the normal supported grid gesture explicitly.

## Live VM acceptance

On the VM, launch a usable Snap fixture from the grid and observe a real input effect. Save a block publicly, require the declared hidden/denied grid result and use the qualified command route for an explicit denial witness when hidden. Restore access through Parent and verify the offered grid entry launches a distinguishable window while any retained activity remains.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_snap_grid
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
