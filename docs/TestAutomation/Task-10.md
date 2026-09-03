### Task 10 — Automate the nested GNOME Shell child preview

- Complexity: high. A Shell extension runs inside the compositor and must be
  tested through supported Shell lifecycle behavior.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: turn the existing Mutter-devkit preview into a repeatable component
  smoke and interaction suite.
- Work:
  1. Refactor `child/preview` into reusable start, readiness, reload, and cleanup
     operations while retaining the interactive developer command.
  2. Start GNOME Shell through the public Mutter devkit in private XDG, settings,
     and D-Bus directories.
  3. Verify that the extension loads, the indicator appears, accessible naming is
     present, the request action launches the shared child overlay, only one
     overlay appears, and clean shutdown produces no Shell warning or critical
     attributable to the extension.
  4. Verify extension reload after source changes through a controlled temporary
     copy, not the developer's live source tree.
  5. Capture the nested Shell log and screenshot as component artifacts.
  6. Update child extension requirement mappings that this environment truthfully
     covers.
- Verification:
  - Run the automated preview three consecutive times.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: the extension is executed inside GNOME Shell 50 under an
  isolated supported preview environment with deterministic cleanup.

