# 047 — Record app activity and compose launch/use

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP04; FLOW08 native usable-app scope**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **035** — APP01/02/03 native grid/command usable scope.
- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement APP04 capture and comparison using explicit immutable public observations. Then compose FLOW08 from the qualified native launch/result/usability blocks. Register only usable-app scope here; policy-denial bindings and retained-user FLOW09/14 are qualified with their respective consumers.

## Live VM acceptance

In a fresh installed VM attempt, enter the child, launch the prepared native app through each qualified route and prove its normal input has a visible effect. Capture a recognizable activity, reread it independently and compare to the earlier immutable observation before further edits. Repeated invocation IDs stay unique; a replaced window cannot pass a same-window comparison. Cross-user retention is a separate qualification.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_app_activity
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
