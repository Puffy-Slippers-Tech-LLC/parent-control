# 044 — Visit retained users and existing windows

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **DESK09; FLOW15 and FLOW01 retained scopes**. First scheduled consumer: [E2E-014, case 40](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **043a** — GDM02 retained-child lock entry; DESK08/11.
- **044a** — DESK10 same-desktop window switching.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement retained-user routing, reusing normal DESK10 window switching and the qualified fresh-child FLOW15 branch. Extend FLOW15 for explicit same/retained/lock/denied entry, and FLOW01 for retained Parent windows without reselection hiding state. Qualify the additional account/recipient bindings required for these entries.

## Live VM acceptance

On the VM, leave recognizable windows on child and Parent desktops, switch between them, unlock normally and foreground the same windows. Wrong entry modes fail without repairing state; compare retained public activity before relaunching anything.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_allowance
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
