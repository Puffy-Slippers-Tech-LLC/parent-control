### Task 10A — Refactor the child preview into reusable orchestration

- Complexity: medium. This is a bounded refactor of development tooling with
  process-lifecycle contracts, but it does not yet automate a live Shell.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Objective: give the interactive preview and later automated tests one
  repository-owned implementation of environment preparation, start,
  readiness, reload, and cleanup behavior.
- Work:
  1. Inspect the current worktree and preserve all completed Task 01 through 09
     changes, especially the child logic and GTK component-test infrastructure.
  2. Extract the monolithic `child/preview` lifecycle into reusable,
     directly-testable orchestration. Keep `child/preview` and
     `make preview-child` as the interactive developer entry point with the
     existing source-watch behavior and user-facing diagnostics.
  3. Represent preview source, private runtime directories, process handles,
     readiness deadlines, reload generations, log destinations, and cleanup as
     explicit inputs or state. Do not inspect or mutate the developer's desktop
     settings, extension installation, or live source files.
  4. Use bounded event-driven process and file waits. Preserve parent-death and
     signal cleanup so an interrupted preview cannot leave GNOME Shell, D-Bus,
     or helper processes running.
  5. Add focused unit and contract tests for environment construction, command
     construction, readiness timeout reporting, reload decisions, cleanup, and
     the interactive wrapper. Process behavior may be represented by controlled
     fakes in this task; live GNOME Shell execution belongs to Task 10B.
  6. Document the reusable boundary sufficiently for Tasks 10B through 10D to
     consume it without duplicating launch or cleanup logic.
- Verification:
  - Run the focused preview-orchestration unit and contract tests.
  - Run `make check` and `git diff --check`.
- Completion criteria: the existing interactive preview uses one tested,
  reusable orchestration boundary, retains its behavior, and no live nested
  Shell automation has been added prematurely.
