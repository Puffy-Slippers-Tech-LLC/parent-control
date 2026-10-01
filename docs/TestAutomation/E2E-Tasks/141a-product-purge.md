# 141a — Qualify purge and reinstall to visible defaults

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 30–50 minutes.

Session exception: Purge, actual activation, usable child access and reinstall-to-defaults must be observed in one fresh qualification.

## Scope and prerequisites

Deliver **LIFE04 purge; LIFE05 notice and reinstall/defaults**. First scheduled consumer: [E2E-027, case 139](../E2E-Scenario-Recipes.md#e2e-027).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **141** — LIFE04 product remove/reinstall; LIFE05 corresponding notices/activation.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the exact verified purge command to AUTH03's administrator authority and
shared guarded SSH package helper, then independently read completion and the
final notice through FILE06. No Terminal or unrelated password prompt is needed.
After ordinary activation, use the qualified install route again before
inspecting fresh defaults. Keep file/account cleanup assertions in existing
mechanical tests.

## Live VM acceptance

In a fresh live attempt, make one public setting nondefault, purge through the shared administrator SSH package helper and follow its actual activation notice. Enter an ordinary child desktop and use the fixture app. Reinstall, follow activation and read the visible fresh default before editing. Require package cleanup checks and owned cleanup; the uninterrupted retained-settings journey remains case 139.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_product_purge
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
