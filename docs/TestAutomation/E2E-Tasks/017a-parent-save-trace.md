# 017a — Observe saving while a Parent control changes

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **PARENT08 transition mode**. First scheduled consumer: [E2E-035, case 159](../E2E-Scenario-Recipes.md#e2e-035).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **017** — PARENT08 snapshot saved/control states; installed qualification and owned cleanup passed.
- **016a** — UI22.
- **016c** — UI25/26 observation during synchronous accessibility input.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

Start at `UiObservations.observe_accessibility_input`, `accessibility_ready`
and `_observe` in `tests/e2e/ui_observations.py`,
`AccessibleUI.parent_checked_events`, `parent_trace_source` and
`parent_save_snapshot` in `tests/e2e/accessible_ui.py`, and
`PublicAtspi.checked_events` in `tests/e2e/public_atspi.py`.
`JourneyPlan.accessibility_inputs` declares the ordinary UI17 action and
terminal; `accessibility_input_trace.PLAN` and
`onpc_feedback_states::run_accessibility_trace` share the qualified sequence.
The Parent checked-state event is qualified, but saving and
conflicting-control samples are not.
Focused lifecycle/refusal checks are `tests/unit/test_e2e_feedback_read.py`,
`tests/unit/test_installed_journey_cleanup_safety.py` and
`tests/unit/test_e2e_progress.py`. The selector below is still unimplemented.

## Session boundary

Compose the qualified 016c observer with the PARENT08 saving/control projection
and ordinary saved snapshot. The extracted prerequisite owns observer lifetime,
event transport and concurrency, not this saving assertion. All original live
outcomes below remain required in a fresh composition qualification.

The 016c observer keeps its input-free public event subscription active during
one synchronous UI17 call. Extend its public projection for this task's
saving/control-state assertion without substituting a final switch value. No
live attempt or product-behavior mismatch has been established for 017a.

## Implementation binding

Bind UI22 to Parent's saving and conflicting-control states. Arm observation and acknowledge readiness before one caller-owned Screen time limit change; collect the trace and terminal saved result without delaying the product.

## Live VM acceptance

On installed Parent, change Screen time limit once with the observer already active. Require the specified saving/control-inhibition samples and final saved state. A missed transient is unproven. Reuse the ordinary snapshot result; a final switch value cannot substitute for the trace.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_parent_save_trace
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
Check **017a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
