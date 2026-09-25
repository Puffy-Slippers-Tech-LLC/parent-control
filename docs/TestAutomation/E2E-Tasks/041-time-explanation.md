# 041 — Read remaining time and configure time controls

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

Reuse `tests/e2e/accessible_ui.py::AccessibleUI.time_explanation(child)` for
PARENT20's read-only observation and `duration_projection` for its compact text,
seconds and one-second precision. `observed_monotonic_ns` uses the guest clock.
`time_explanation_operation` keeps the qualified explicit collapse/expand
preparation separate; PARENT09 must add its conditional behavior without making
PARENT20 navigate. The existing qualification is `tests/e2e/time_explanation.py::PLAN`,
`tests/integration/graphical_smoke/lib/onpc_time_explanation.pm::run` and
`tests/integration/parent_setup_qualification.py::TimeExplanationQualification`.
Reuse `allowance_preset`, `custom_allowance`, `parent_save_snapshot` and `settings`
for ordinary allowance setup. Adapter checks are in
`tests/unit/test_accessible_e2e_ui.py`, worker/controller checks in
`tests/unit/test_e2e_toggle.py`, and real GTK projections in
`tests/ui/test_preview_smoke.py::test_parent_remaining_time_explanation`.
The live selector below is planned, not yet implemented or registered.

## Scope and prerequisites

Deliver **PARENT09, FLOW02**. First scheduled consumer: [E2E-036, case 161](../E2E-Scenario-Recipes.md#e2e-036).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **194** — PARENT20.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Implement PARENT09's non-collapsing expanded explanation first. Compose FLOW02 with conditional enable, allowance commit/save, explicit final enablement, settings and explanation. Disabling clears a grant and is never navigation.

## Live VM acceptance

On the VM, configure positive then zero daily allowance and read daily/one-time/total explanations. Repeated PARENT09 reads leave the section expanded. Compare displayed values with rounding bounds and observe real saves.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_time_explanation
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
Check **041** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
