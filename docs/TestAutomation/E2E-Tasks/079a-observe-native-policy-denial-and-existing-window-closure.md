# 079a — Observe closure of an already-open native app

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add independently observed closure of an earlier captured native activity after saving a block. Reuse 079d's new-launch results and preserve the unaffected target.

Tasks **079d** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **APP02 and FLOW08 native grid/command policy results**. First scheduled consumer: [E2E-005, case 7](../E2E-Scenario-Recipes.md#e2e-005).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **047** — APP04; FLOW08 native usable-app scope.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **079d** — APP02 and FLOW08 native grid/command blocked-launch results.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify native grid/command usable, hidden-launcher, explicit denial and prior-window closure projections. Extend FLOW08 only after APP02 is qualified. A hidden grid entry uses a separately declared command attempt to prove denied execution. APP03 runs only for usable access.

## Live VM acceptance

On the installed VM, open a native activity permissively and capture its public window. Save a block in Parent, return normally and require that earlier window's closure and a denied new launch. Check Allowed, Hard and Soft with no soft exception, plus an unaffected allowed target. Reapplying a block cannot be hidden by relaunching the old activity.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_observe_native_policy_denial_and_existing_window_closure
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
