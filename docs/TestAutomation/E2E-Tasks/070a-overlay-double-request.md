# 070a — Observe one prompt after an overlay double-click

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **REQUEST10 overlay binding**. First scheduled consumer: [E2E-014, case 38](../E2E-Scenario-Recipes.md#e2e-014).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **070** — UI20; REQUEST10 kiosk binding.
- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Complete the overlay UI duration matrix before the customer cases: every preset,
all valid/invalid custom values and exact estimates from the recipe table. Reuse
the shared kiosk/overlay selection, input and public-read operations; installed
cases sample one value while retaining real authorization and time assertions.

Bind the existing double-click and public trace projections to the overlay's Request control and desktop agent. Do not reimplement the gesture or widen the kiosk qualification.

## Live VM acceptance

On a live child desktop with publicly prepared usable time, double-click Request once. Observe the declared inhibition trace and exactly one prompt/form, then finish through qualified approval and automatic overlay exit. Hidden/disabled controls must refuse the gesture.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_overlay_double_request
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
