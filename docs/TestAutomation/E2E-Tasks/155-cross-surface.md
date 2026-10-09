# 155 — Compare kiosk choices at each child overlay

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add kiosk-to-overlay for both children. Reuse 155a's comparisons; keep direction-specific approvers and no-approval scope.

Reuse the delivered scope of tasks **155a** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **FLOW12 current choices**. First scheduled consumer: [E2E-018, case 60](../E2E-Scenario-Recipes.md#e2e-018).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **155a** — FLOW12 overlay-to-kiosk choices for both children.

Its transitive prerequisites retain overlay choices/duration/validation and
Cancel/Escape operations, retained desktop entry and public Parent allowance setup.

## Implementation

Add the kiosk-to-overlay FLOW12 direction using 155a's shared request exit, entry and REQUEST03/UI12 comparison operations. Duration, custom value and soft-app choice follow the child; the station and each overlay keep their own approver. Qualify both child bindings and read the destination before editing. This composition performs no approval.

## Live VM acceptance

In fresh guarded VM attempts, publicly enable both children with ample time. Seed the recipe's different kiosk values and local approvers, then compare each child's kiosk-to-overlay result before changing any destination choice. Finish with that destination form open; preserve independent valid entry and wrong-child/surface refusal. Reuse 155a's unchanged exact overlay-to-kiosk qualification, rerunning affected branches when necessary; its evidence supplies no saved VM state. Current mute absence has no interactive value; deferred mute does not block this task.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_cross_surface
```
