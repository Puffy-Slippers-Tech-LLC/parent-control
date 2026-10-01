# 155 — Compare kiosk choices at each child overlay

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add kiosk-to-overlay for both children. Reuse 155a's comparisons; keep direction-specific approvers and no-approval scope.

Tasks **155a** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **FLOW12 current choices**. First scheduled consumer: [E2E-018, case 60](../E2E-Scenario-Recipes.md#e2e-018).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.
- **155a** — FLOW12 overlay-to-kiosk choices for both children.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Compose FLOW12 in each direction from the declared request exit, entry and REQUEST03/UI12 comparisons. Duration, custom value and soft-app choice follow the child; the station and each overlay keep their own approver. Qualify both children and read the destination before editing. This composition performs no approval.

## Live VM acceptance

On the VM, publicly enable both children with ample time. Seed the recipe's different values and local approvers, then compare overlay→kiosk and kiosk→overlay before changing any selection. Each route must finish with the destination form open. Current mute absence has no interactive value; deferred mute does not block this task.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_cross_surface
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
