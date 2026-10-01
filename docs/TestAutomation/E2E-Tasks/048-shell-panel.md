# 048 — Qualify direct and panel entry to the child overlay

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **DESK12, REQUEST02 direct entry, REQUEST13 panel entry and REQUEST03 overlay readback**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.
- **011** — REQUEST01, REQUEST03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify normal unlocked-child panel routing (DESK12). For ordinary overlay entry, invoke the installed child command through REQUEST02 and independently observe form count and fixed child with REQUEST03. Separately qualify REQUEST13's graphical panel entry for E2E-012's explicit launch and singleton check. Reuse the shared immutable reader. Choice editing, exits and authentication are separately qualified bindings; fullscreen reveal belongs to its game consumer.

## Live VM acceptance

On the VM with publicly prepared usable child time and fresh child entry, directly invoke the child command and observe exactly one form with the intended fixed child and readable controls. Cancel and repeat from an independently reached child desktop. In a separate entry, activate the panel request control twice deliberately and observe exactly one form with the same fixed child. Use normal Cancel solely to end qualification; this does not qualify the reusable exit binding. Never select another overlay child.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_shell_panel
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
