# 079a — Observe native policy denial and existing-window closure

Estimate: 35–55 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **APP02 and FLOW08 native grid/command policy results**. First scheduled consumer: [E2E-005, case 7](../E2E-Scenario-Recipes.md#e2e-005).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **047** — APP04; FLOW08 native usable-app scope.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify native grid/command usable, hidden-launcher, explicit denial and prior-window closure projections. Extend FLOW08 only after APP02 is qualified. A hidden grid entry uses a separately declared command attempt to prove denied execution. APP03 runs only for usable access.

## Live VM acceptance

On the installed VM, open a native activity permissively and capture its public window. Save a block in Parent, return normally and require that earlier window's closure and a denied new launch. Check Allowed, Hard and Soft with no soft exception, plus an unaffected allowed target. Reapplying a block cannot be hidden by relaunching the old activity.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_app_policy
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
