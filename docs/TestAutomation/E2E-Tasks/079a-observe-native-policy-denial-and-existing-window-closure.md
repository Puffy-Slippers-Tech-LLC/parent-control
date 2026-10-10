# 079a — Observe closure of an already-open native app

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add independently observed closure of an earlier captured native activity after saving a block. Reuse 079d's new-launch results and preserve the unaffected target.

Reuse the delivered scope of tasks **079d** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **APP02 and FLOW08 native grid/command policy results**. First scheduled consumer: [E2E-006, case 13](../E2E-Scenario-Recipes.md#e2e-005).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079d** — APP02 and FLOW08 native grid/command blocked-launch results.
- **044** — Legitimate return to the captured child desktop after the Parent save.

## Implementation

Reuse 079d's native grid/command usable, hidden-launcher and explicit-denial projections. Add the prior-window-closure result to APP02/FLOW08. A hidden grid entry retains its separately declared command attempt to prove denied execution. APP03 runs only for usable access.

## Live VM acceptance

In a fresh guarded VM attempt, open a native activity permissively and capture its public window. Save each declared Hard and Soft block with no soft exception in Parent, return normally and require that earlier window's closure and a denied new launch, plus an unaffected Allowed target. Qualify independent valid entry and wrong-activity/owner refusal. Reapplying a block cannot be hidden by relaunching the old activity. Reuse 079d's unchanged exact no-prior-window launch-result qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_observe_native_policy_denial_and_existing_window_closure
```
