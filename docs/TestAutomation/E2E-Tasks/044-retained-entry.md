# 044 — Visit both retained child desktops

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add both retained child bindings and complete explicit FLOW15 modes. Reuse 044b's Parent entry; keep other-parent management under task 198.

Tasks **044b** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **DESK09; FLOW15 and FLOW01 retained scopes**. First scheduled consumer: [E2E-014, case 40](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043a** — GDM02 retained-child lock entry; DESK08/11.
- **044a** — DESK10 same-desktop window switching.
- **044b** — DESK09 and FLOW01 retained Parent entry.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement retained-user routing, reusing normal DESK10 window switching and the qualified fresh-child FLOW15 branch. Extend FLOW15 for explicit same/retained/lock/denied entry, and FLOW01 for retained Parent windows without reselection hiding state. Qualify the Parent and both child account/recipient bindings required for these entries. A retained Parent window may be on App Limits: reach Screen Limits with PARENT04 before reading PARENT03. The second administrator's management desktop/window remains the separate other-parent scope.

## Live VM acceptance

On the VM, leave recognizable windows on child and Parent desktops, switch between them, unlock normally and foreground the same windows. Wrong entry modes fail without repairing state; compare retained public activity before relaunching anything.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_retained_entry
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
