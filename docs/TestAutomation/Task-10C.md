### Task 10C — Automate child indicator request interaction

- Complexity: high. The assertion crosses an accessible Shell actor, extension
  single-flight state, a spawned GTK process, and two compositor-visible
  surfaces.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: prove that the real nested-Shell indicator launches exactly one
  shared child request overlay through supported user interaction.
- Work:
  1. Extend Task 10B's harness with semantic interaction through the indicator's
     accessible action or supported virtual input. Do not use host-window
     coordinates, Looking Glass evaluation, private Shell internals, or a
     production D-Bus test hook.
  2. Add an explicit preview scenario that leaves the overlay closed until the
     indicator is activated. Keep this preview-only fixture behavior separate
     from production startup and retain the interactive preview's current
     default behavior.
  3. Activate the indicator and verify that the production extension launches
     the existing shared GTK request form in child-overlay mode. Reuse the Task
     08 component surface and accessibility contract rather than implementing a
     second form or a Shell-only substitute.
  4. Attempt repeated activation while the request is opening and while it is
     running. Assert from observable process, accessibility, and window state
     that only one overlay exists and only one request-launch event occurred.
  5. Close the overlay through its supported UI behavior, verify the extension
     clears active state, and verify a later activation can open one new overlay.
  6. Preserve complete, redacted Shell and overlay diagnostics on failure and
     retain deterministic cleanup for both processes.
- Verification:
  - Run the focused nested-Shell interaction test in three consecutive fresh
    processes through `tools/run-ui-tests --timeout <duration> ...`.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: a semantic interaction with the real Shell indicator
  opens the shared child overlay, repeated interaction cannot create a duplicate,
  and the flow can close and reopen cleanly in three consecutive runs.
