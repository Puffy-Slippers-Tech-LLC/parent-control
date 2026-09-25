# 029 — Open feedback and read synthetic drafts

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **FEED01, FEED03**. Complete feedback consumer: [E2E-031, case 152](../E2E-Scenario-Recipes.md#e2e-031).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

Required tasks: none (Baseline). Use the existing qualified source interfaces
and guarded attempt envelope; unqualified provider bindings remain unavailable.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

Source: `AccessibleUI.open_feedback`, `feedback_snapshot` and
`feedback_read_operation` in `tests/e2e/accessible_ui.py`;
`FeedbackObservation` in `tests/e2e/ui_observations.py`;
`tests/e2e/feedback_read.py` and `onpc_feedback_read.pm` compose the slice.
The initial observation permits only empty body/reply, the sole diagnostic ZIP,
successful collection and initial control/validation states. Nonempty drafts,
attachments and other collection states remain future bindings.
Host checks: `tests/unit/test_e2e_feedback_read.py`,
`tests/unit/test_installed_journey_cleanup_safety.py`,
`tests/unit/test_test_launchers.py` and `tests/unit/test_e2e_progress.py`;
real-editor regression:
`tests/ui/test_e2e_accessible_adapter.py::test_feedback_read_adapter_uses_real_public_editor`.

Blocker: app-snapshot preparation stopped before VM work because two unrelated
`write-e2e` cleanup prerequisites expect `duration=N minutes` but receive
`duration=0m`. See [the prerequisite report](../../../output/test-runs/host/reports/20260925T002355Z-61aea90d/report.md).
Resume when the launcher expectations and implementation are reconciled and
prerequisites pass. The feedback adapter repairs pass
[host validation](../../../output/test-runs/host/reports/20260925T002159Z-f8f68c58/report.md);
installed acceptance still needs a fresh guarded attempt.

## Implementation

Register feedback editor, body/reply, attachments, validation and collection snapshots. Implement FEED01 entry and FEED03 immutable bounded synthetic observations. Keep Send untouched.

## Live VM acceptance

In installed Parent, open feedback and observe editor readiness, initial draft, exact attachment set and control states. Repeat FEED03 from an independently opened dialog; private drafts and arbitrary text projections remain unavailable.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_feedback_read
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After this slice's live qualification and cleanup, follow the
[master completion contract](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Update the relevant callable/scope/status in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and update the selected recipe only when
its composition changes. Runtime status belongs in the inventory; leave
unfinished scope pending.
Check **029** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
