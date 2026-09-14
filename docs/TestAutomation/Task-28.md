# Task 28 — Coverage acceptance and operator handoff

The [master checklist](Test-Automation.md#unfinished-tasks) prioritizes customer
journeys, then mechanical package qualification. Existing regression suites
remain intact. Completion must describe those scopes separately and preserve
unresolved product-design blockers.

## Implementation slices

Use actual existing commands and recorded runtime evidence. No new general CI,
cache, scheduler or evidence framework is a prerequisite for customer coverage.
The [daily guide](../Test-Automation.md#daily-commands) distinguishes current
commands from planned interfaces.

## Task 28A

- Title: Deferred broad command, CI and artifact-reuse expansion.
- Status: outside the automatic queue; no standalone implementation now.
- Retained work: four-command dispatch, broad CI integration, complete build-input
  closure, reproducibility coordination and safe caching remain unaccepted where
  not already implemented. Preserve existing code/tests and published interfaces.
- A named consumer may require a minimal adapter over the current validated
  runner; implement only that need with its consumer. Do not widen approvals,
  replace working selectors or add another execution framework.
- Task 20's [R1 recovery](Task-20.md#bounded-recovery--2026-09-11) still owns
  demonstrated input-stability/validation-timing repairs and their cumulative
  checkpoints. This separation does not bypass or reset those safeguards.

## Task 28B

- Title: Review executed customer and mechanical package coverage.
- Depends on: active customer tasks and Tasks 18/20, with blocked cases explicit.
  Deferred engineering is not silently treated as completed.
- Default settings: `gpt-6-astra` / `high` for the scoped acceptance review.
- Work:
  1. Compare the frozen customer inventory with actual complete executions and
     visible evidence. Cover every app surface and distinct customer behavior,
     including both request forms, real gameplay and continuous family journeys.
     Do not limit the audit to the timeout/login example.
  2. Confirm every customer action/assertion could be performed/observed by a
     real user. Remove no passing existing lower-level test; instead correct
     wrong E2E claims and classify internal qualification separately.
  3. Verify that scope transfers, duplicate removal and helper passes were not
     counted as completed customer variants. Preserve missing, blocked, failed,
     skipped and partial results; no simulated/internal substitute can pass.
  4. Review mechanical Tasks 18/20 independently for their required internal
     installation, migration, removal and recovery evidence. Surface-only
     customer success does not waive mechanical failures.
  5. Use the currently implemented validated suite/selector commands for the
     required current-input checks, retaining all established regression and
     safety suites. If a comprehensive command is unavailable, report the
     actual selected scope; do not claim an unexecuted full-suite/release pass
     or launch a general infrastructure project from this review.
  6. Record completed customer scope, mechanical scope and separate unresolved
     engineering/product blockers. An applicable demonstrated release blocker
     requires a product decision; it is not erased by green customer scenarios.
- Verification/completion: the active scope has truthful executed coverage and
  current-run evidence, with existing cleanup and required regressions passing.
  Mark complete only when that stated acceptance is met. This is not a claim
  that every deferred internal guarantee or the entire specification is proven.

## Task 28C

- Title: Document the verified workflow and remaining limits.
- Depends on: Task 28B's accepted result or explicit blocked handoff for the
  operator; a blocked acceptance must remain labeled blocked.
- Default settings: `gpt-5.6-luna` / `low` for settled documentation.
- Work:
  1. Document the actual supported commands/selectors, preparation, safe artifact
     inspection, visible scenario coverage and mechanical package coverage.
  2. Link existing run evidence, pending cases and separate engineering blockers.
     Distinguish completed scenarios from harness qualification and scope moves.
  3. Check links, references and whitespace. Do not rerun runtime suites for
     documentation-only work or claim that planned commands are implemented.
- Completion criteria: the operator can run and interpret the verified scope,
  and can see what remains unaccepted without reading session histories.
