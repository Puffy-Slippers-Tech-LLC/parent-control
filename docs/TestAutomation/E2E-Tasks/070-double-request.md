# 070 — Double-click kiosk Request and observe one prompt

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI20; REQUEST10 kiosk binding**. First scheduled consumer: [E2E-014, case 41](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **020** — AUTH02 and REQUEST11/12 kiosk approval/rejection/cancel and both approved exits.
- **016a** — UI22.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Complete the kiosk UI duration matrix before the customer cases: every preset,
all valid/invalid custom values and exact estimates from the recipe table. Reuse
the same selection/input/read blocks in preview and installed tests. UI owns
these local permutations; the live slice below owns real prompt concurrency.

Implement one deliberate native double-click gesture first. Surround it with UI22 prompt/form-count and Request availability traces; REQUEST10 also independently checks final counts. No input repair or internal exactly-once claim.

## Live VM acceptance

On the live kiosk, double-click an enabled Request once and observe one prompt plus the declared inhibition/count trace, then finish through the qualified agent. Disabled/hidden controls never receive the gesture. Overlay binding remains a separate slice.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_double_request
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
