# 180 — Set an allowance for a named child

Estimate: 15–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

Reuse `tests/e2e/accessible_ui.py::AccessibleUI.configure_time_controls` for
FLOW02's qualified 0/15-minute presets and explicit initial/final enablement.
It returns PARENT09's explanation after saved-settings validation;
`reach_time_explanation(child)` conditionally expands, while
`time_explanation(child)` remains the read-only PARENT20 observer.
The existing qualification is `tests/e2e/time_explanation.py::PLAN` with
`tests/integration/graphical_smoke/lib/onpc_time_explanation.pm::run` and
`tests/integration/parent_setup_qualification.py::TimeExplanationQualification`.
Adapter/controller checks are in `tests/unit/test_accessible_e2e_ui.py` and
`tests/unit/test_e2e_toggle.py`; real GTK expansion checks are in
`tests/ui/test_preview_smoke.py::test_parent_remaining_time_explanation`.
These do not yet qualify FLOW01 same-user entry or FLOW16. The live selector
below is planned and must be implemented and registered before use.

## Scope and prerequisites

Deliver **FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup**. First scheduled consumer: [E2E-036, case 161](../E2E-Scenario-Recipes.md#e2e-036).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **041** — PARENT09, FLOW02.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Qualify FLOW01's same-user Parent entry first, then compose FLOW16 from explicit parent/child/source/window entry and FLOW02's initial allowance/final limit state. Keep navigation and final Parent surface explicit; retained and second-parent bindings use their separately qualified entry scopes.

## Live VM acceptance

On installed Parent, use fresh/new and independently open same-user entries to set the selected child's allowance to zero and then an ordinary positive value. Read saved settings and balances without logging out implicitly. Wrong selected-child/window input must refuse.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_set_an_allowance_for_a_named_child
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
Check **180** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
