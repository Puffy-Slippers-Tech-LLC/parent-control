# 141 — Reinstall after removal and follow activation

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: The complete removal/reinstall activation route and package cleanup checks remain required after reusing the qualified removal operation.

## Session boundary

Add verified reinstall, its activation notice and Parent re-entry after removal. Reuse 141b's remove/reboot route; full retained-settings lifecycle stays in case 139.

Reuse the delivered scope of tasks **141b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation**. First scheduled consumer: [E2E-027, case 139](../E2E-Scenario-Recipes.md#e2e-027).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **007** — LIFE02.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **014** — FLOW04 kiosk.
- **141b** — LIFE04 remove and LIFE05 removal activation.

## Implementation

Bind the exact verified remove and reinstall commands, permitted prompts and
completion/reboot notices. Compose the corresponding LIFE05 notice/reboot path from the qualified LIFE02/GDM07 operations, and keep mechanical file,
account and migration checks under their existing system owners. Purge and
fresh-default observation are a separate capability.

## Live VM acceptance

On the live VM, remove the product through the shared administrator SSH package helper, read the final reboot-required text, reboot normally and enter the child desktop to use the prepared app. Reinstall, follow the actual activation notice and open Parent. Require affected package cleanup checks and owned cleanup; case 139 owns the complete retained-settings lifecycle.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_product_removal
```
