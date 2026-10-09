# 109 — Observe Snap command denial and closure

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add publicly configured Hard/Soft command denial and expected closure, preserving usable A. Reuse 109b's activity and new-window route; do not reimplement package installation.

Reuse the delivered scope of tasks **109b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Snap command route**. First scheduled consumer: [E2E-019, case 92](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **109b** — APP01/02/03/04 and FLOW08 Snap command usable/new-window route.

## Implementation

Verify the qualified Snap baseline profile from task 109p in a fresh attempt.
Reuse 109b's fixed Snap command, supported new-window, APP03 usability and APP04
activity operations. Add APP02 Hard/Soft denial and prior-window closure to
FLOW08 while preserving the unaffected usable A. Use the repository-owned
fixture IDs; an existing window cannot pass a new launch. Package installation
is already qualified and must not be reimplemented here.

## Live VM acceptance

On the VM, capture the required activity through 109b's qualified Snap command
route. Apply the declared Hard and Soft blocks through Parent and require
explicit command denial and the expected prior-window closure, with A still
usable. Reuse unchanged exact launch/use and separate-window qualification from
109b; rerun affected branches when necessary. Its evidence supplies no saved VM
state: qualify the new policy composition in a fresh guarded attempt with
independent valid entry and wrong-fixture/owner refusal. Missing supported assets
or independent public policy observations block the affected consumer.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_snap
```
