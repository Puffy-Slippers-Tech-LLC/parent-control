# 194 — Read an expanded time explanation

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

Reuse the ordinary allowance callables in `tests/e2e/accessible_ui.py`:
`allowance_preset`, `custom_allowance`, `settings` and `parent_save_snapshot`.
The qualification composition is `tests/e2e/allowance.py::PLAN` and
`tests/integration/graphical_smoke/lib/onpc_allowance.pm::run`; its guarded
entry is `tests/integration/parent_setup_qualification.py::AllowanceQualification`.
PARENT03 reads custom numbers from `parent-custom-daily-limit`; the selector
itself displays only `Custom value`. Keep PARENT20 read-only and separate from
the explicit expansion used to prepare its entry. Adapter regressions live in
`tests/unit/test_accessible_e2e_ui.py`; the maintained real GTK allowance setup
is `tests/ui/test_preview_smoke.py::test_parent_daily_preset_and_custom_limit_autosave`.
The live selector below remains planned until implemented and registered.

## Scope and prerequisites

Deliver **PARENT20**. First scheduled consumer: [E2E-036, case 161](../E2E-Scenario-Recipes.md#e2e-036).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **040** — PARENT05/06 valid ordinary values.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Register daily, one-time and total text projections, display precision and monotonic observation time. Read only an already expanded showing explanation; expansion/navigation belongs to PARENT09.

## Live VM acceptance

On installed Parent, enable limits and save an ordinary allowance. Explicit UI inputs expand the explanation before PARENT20 is called; independently read all three balances twice without changing expanded state. A collapsed explanation or wrong child refuses without opening it.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_read_an_expanded_time_explanation
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
Check **194** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
