# 109 — Observe Snap command denial and closure

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add publicly configured Hard/Soft command denial and expected closure, preserving usable A. Reuse 109b's activity and new-window route; do not reimplement package installation.

Tasks **109b** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Snap command route**. First scheduled consumer: [E2E-019, case 92](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **109p** — Snap baseline assets and verification; FIX04 transfer only.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **109b** — APP01/02/03/04 and FLOW08 Snap command usable/new-window route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Verify the qualified Snap baseline profile from task 109p in a fresh attempt.
Qualify APP01/02/03 for the fixed Snap command route, then APP04 activity identity
and FLOW08. Register the supported new-window command so presenting an existing
window cannot pass a new launch. Use the repository-owned fixture IDs. Package
installation is already qualified and must not be reimplemented here.

## Live VM acceptance

On the VM, use the declared Snap command to launch each required fixture and observe normal input effects. Capture S, open a distinguishable second instance and prove the earlier activity remains. Through Parent, apply Hard and Soft blocks and require explicit command denial and the expected closure, with A still usable. A missing supported asset, new-instance route or public observation blocks the affected consumer.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_snap
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
