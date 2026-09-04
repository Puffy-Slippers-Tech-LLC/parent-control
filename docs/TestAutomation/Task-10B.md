### Task 10B — Add the isolated nested-Shell lifecycle smoke

- Complexity: high. This task crosses GNOME Shell, Mutter Devkit, private D-Bus,
  AT-SPI, GSettings, and subprocess shutdown boundaries.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: execute the production child extension inside GNOME Shell 50 in a
  deterministic, isolated component-test environment.
- Work:
  1. Build the live component harness on Task 10A's orchestration. Start GNOME
     Shell through its public `--devkit` path and Mutter Devkit; do not use the
     removed legacy nested backend or any private Shell evaluation API.
  2. Give each run private XDG data, config, cache, state, and runtime
     directories; a private settings backend and compiled schema directory; a
     private session D-Bus; and a private AT-SPI registry. Do not inherit or
     alter host extension settings.
  3. Copy the packaged extension layout into the run directory. Automated runs
     must not symlink modules back to the live checkout.
  4. Wait with bounded readiness conditions for the private bus, Shell,
     extension activation, accessibility registration, and the visible
     remaining-time indicator. Assert the indicator's accessible request name.
  5. Shut down every owned process deterministically and fail on a leak. Inspect
     the complete Shell log and fail on warnings, criticals, or JavaScript errors
     attributable to this extension, while retaining enough redacted context to
     diagnose an unrelated platform failure.
  6. Add a stable focused command, such as `make check-child-shell`, and include
     the lifecycle smoke in `make check-component` without making `make check`
     depend on a graphical compositor.
- Verification:
  - Run the focused nested-Shell lifecycle smoke in three consecutive fresh
    processes through `tools/run-ui-tests --timeout <duration> ...`.
  - Run `make check-component`, `make check`, and `git diff --check`.
- Completion criteria: GNOME Shell 50 loads the extension from a disposable copy,
  exposes the indicator semantically, and exits without extension-attributable
  warnings or leaked processes in three consecutive runs.
