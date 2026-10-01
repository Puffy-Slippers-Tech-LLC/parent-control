# 141 — Reinstall after removal and follow activation

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 30–50 minutes.

Session exception: The complete removal/reinstall activation route and package cleanup checks remain required after reusing the qualified removal operation.

## Session boundary

Add verified reinstall, its activation notice and Parent re-entry after removal. Reuse 141b's remove/reboot route; full retained-settings lifecycle stays in case 139.

Tasks **141b** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation**. First scheduled consumer: [E2E-027, case 139](../E2E-Scenario-Recipes.md#e2e-027).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **007** — LIFE02.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **014** — FLOW04 kiosk.
- **141b** — LIFE04 remove and LIFE05 removal activation.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the exact verified remove and reinstall commands, permitted prompts and
completion/reboot notices. Compose the corresponding LIFE05 notice/reboot path from the qualified LIFE02/GDM07 operations, and keep mechanical file,
account and migration checks under their existing system owners. Purge and
fresh-default observation are a separate capability.

## Live VM acceptance

On the live VM, remove the product through the shared administrator SSH package helper, read the final reboot-required text, reboot normally and enter the child desktop to use the prepared app. Reinstall, follow the actual activation notice and open Parent. Require affected package cleanup checks and owned cleanup; case 139 owns the complete retained-settings lifecycle.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_product_removal
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
