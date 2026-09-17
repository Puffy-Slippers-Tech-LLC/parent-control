# 109 — Qualify Snap fixtures and command launches

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **FIX04 Snap assets; APP01/02/03/04 and FLOW08 command route**. First scheduled consumer: [E2E-019, case 92](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **079a** — APP02 and FLOW08 native grid/command policy results.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind supported pinned Snap A/H/S fixtures and their public activity projections through FIX04. Qualify the fixed command route in APP01/02/03, then APP04 identity/activity comparison and FLOW08. Register a supported new-window command so returning an existing window cannot pass a fresh-launch check. Reuse the native adapters where their public contract applies.

## Live VM acceptance

On the VM, use the declared Snap command to launch each required fixture and observe normal input effects. Capture S, open a distinguishable second instance and prove the earlier activity remains. Through Parent, apply Hard and Soft blocks and require explicit command denial and the expected closure, with A still usable. A missing supported asset, new-instance route or public observation blocks the affected consumer.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_snap
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
