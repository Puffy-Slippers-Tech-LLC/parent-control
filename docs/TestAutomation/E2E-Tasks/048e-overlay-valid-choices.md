# 048e — Choose valid overlay values and Cancel

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **REQUEST04/05/06/08 overlay valid choices and REQUEST11/12 Cancel**. Named consumer: task **048a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048** — DESK12, REQUEST02 direct entry, REQUEST13 panel entry and REQUEST03 readback.
- **014** — FLOW04 kiosk.
- **047** — APP04; FLOW08 native usable-app scope.

## Implementation

Bind fixed-child overlay approver/duration/custom/soft-app values and independent estimates. Reuse shared kiosk operations with overlay IDs, and bind Cancel back to the earlier child activity.

## Live VM acceptance

With usable child time, capture app activity, open the overlay, edit each valid choice and read it back. Cancel and require the same usable activity. Reject child reselection and wrong-surface input.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_valid_choices
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
