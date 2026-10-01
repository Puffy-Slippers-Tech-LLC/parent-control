# 048b — Complete overlay exits and approval compositions

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add immediate approved exit to the same activity, then compose overlay FLOW05/07. Reuse 048f's rejection/Cancel and 048d's automatic return.

Tasks **048f** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07**. First scheduled consumer: [E2E-015, case 46](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **021** — FLOW05/06/07 kiosk.
- **048c** — Shell Polkit AUTH01 overlay recipient and guarded Cancel/preserved-form result.
- **048d** — AUTH02 overlay approval; REQUEST11/12 success and automatic child return.
- **048f** — AUTH02 overlay rejection/Cancel and preserved-form readback.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse task 048c's Shell recipient/Cancel binding, task 048d's sealed submission,
approval and automatic child return, and task 048f's rejection/Cancel with
preserved choices. Add immediate approved exit and compose overlay FLOW05/07
from those shared leaves; MATE proofs never authorize Shell input.

## Live VM acceptance

In separate live overlay attempts, enter one declared wrong password and observe explicit rejection, Cancel and compare the usable unchanged form; separately Cancel a fresh challenge. Approve another declared request and take the offered immediate exit after reading success, returning to the same child activity. Keep valid automatic-return evidence from 048d and rerun it when changed code affects it. Refuse wrong provider/request, stale or reused proof and uncertain delivery; require sealed capture, collection and cleanup.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_overlay_approval
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
