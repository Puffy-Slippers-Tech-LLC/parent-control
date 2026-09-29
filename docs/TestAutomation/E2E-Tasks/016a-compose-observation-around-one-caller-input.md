# 016a — Compose observation around one caller input

Estimate: 15–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Read only the named block rows/callables, this recipe's selected cases and
applicable finite-data rows. Prerequisite IDs are completion checks; do not open
their task briefs. Do not load the full queue, catalogue, recipe book or inventory.

## Scope and prerequisites

Deliver **UI22**. First scheduled consumer: [E2E-035, case 159](../E2E-Scenario-Recipes.md#e2e-035).
Read the named [block contracts](../E2E-Building-Blocks.md#public-observations-and-individual-inputs), [related block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **016** — UI25/26 trace start/readiness and finish.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

Start at `UiObservations.start_trace`, `poll_trace` and `finish_trace` in
`tests/e2e/ui_observations.py`, `JourneyPlan.trace_bindings` and the idle-worker
pump in `tests/e2e/installed_journey.py`, and `trace_transition.PLAN` /
`onpc_feedback_states::transition_trace`. The qualified binding is only empty
Parent feedback to `body-first`, with prefix samples during caller input and
terminal validation/control checks; the valid-to-invalid binding below is not
yet implemented. Preserve the stable-state route and immutable sample evidence.
Focused host checks are `tests/unit/test_e2e_feedback_read.py`,
`tests/unit/test_installed_journey_cleanup_safety.py` and
`tests/unit/test_e2e_progress.py`. Retained live selectors are
`check_e2e_trace`, `check_e2e_trace_stable_state` and `check_e2e_feedback_states`.
The task-local selector below remains unimplemented until this task registers it.

## Implementation

Compose UI25 → the caller's explicitly declared input → UI26. Pass the token and expected terminal predicate explicitly. Preserve input-once behavior and reuse the existing worker/controller channel.

## Live VM acceptance

On installed feedback, bracket one valid-to-invalid body edit with UI22 and read the resulting public validation/control samples. Independently compare the final FEED09 snapshot. Failed trace readiness must prevent input; uncertain input must never be replayed.

Run affected safety/adapter checks, then implement and register the fixed slice
qualification below in the existing guarded envelope. Run this slice here;
its complete scenario remains a separate queue task:

```sh
tools/run-tests integration check_e2e_compose_observation_around_one_caller_input
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
Check **016a** in the [master's queue](../E2E-Task-Queue.md), update the master's
**Next task** pointer, then delete this brief once its enduring context is maintained
in source/contracts. Validate changed Markdown. Keep normal runner artifacts;
no task archive, evidence document or accumulated history.
