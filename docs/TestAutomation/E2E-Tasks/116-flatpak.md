# 116 — Observe Flatpak command denial and closure

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add publicly configured Hard/Soft command denial and expected closure, preserving usable A. Reuse 116b's activity and new-window route; do not reimplement package installation.

Reuse the delivered scope of tasks **116b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Flatpak command route**. First scheduled consumer: [E2E-019, case 104](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **116p** — Flatpak baseline assets and FIX06 verification.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **116b** — APP01/02/03/04 and FLOW08 Flatpak command usable/new-window route.

## Implementation

Verify the qualified Flatpak baseline profile from task 116p in a fresh attempt.
Qualify APP01/02/03 for the fixed Flatpak command route, then APP04 activity identity
and FLOW08. Register the supported new-window command so presenting an existing
window cannot pass a new launch. Use repository-owned fixture IDs. Preserve the
qualified installation scope; do not add package installation to this slice.

## Live VM acceptance

On the VM, use the declared Flatpak command to launch each required fixture and observe normal input effects. Capture S, open a distinguishable second instance and prove the earlier activity remains. Through Parent, apply Hard and Soft blocks and require explicit command denial and the expected closure, with A still usable. A missing supported asset, new-instance route or public observation blocks the affected consumer.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_flatpak
```
