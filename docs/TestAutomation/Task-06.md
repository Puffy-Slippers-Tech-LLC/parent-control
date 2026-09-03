### Task 06 — Establish modern hermetic GTK automation

- Complexity: medium-high. Wayland input, accessibility selectors, and GTK4
  lifecycle handling must be deterministic.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: create a maintained semantic UI harness for GTK component tests.
- Work:
  1. Pin current Dogtail 2.x with hashes in the isolated test-tool environment.
     Do not use Ubuntu's legacy Dogtail 1.x package.
  2. Use Dogtail's hermetic session support with a private D-Bus, private AT-SPI
     bus, bare Mutter compositor, virtual monitor, and deterministic GTK theme,
     scale, locale, and animation settings.
  3. Use the maintained Ubuntu `gnome-ponytail-daemon` package for real Wayland
     session runs that require injected pointer or keyboard input.
  4. Add stable accessible names and descriptions to all important Parent and
     request-form controls. These identifiers must be meaningful accessibility
     metadata, not hidden test IDs.
  5. Add reusable pytest fixtures for launching an app, waiting for an
     accessibility node, taking a screenshot, collecting application logs, and
     shutting the hermetic session down cleanly.
  6. Add a minimal smoke test for Parent preview, kiosk preview, and child-overlay
     preview. Parameterize shared-form checks across both request modes.
  7. Add `make check-component` without changing `make check` into a graphical
     or privileged command.
- Verification:
  - Run the smoke tests three consecutive times.
  - Confirm no process, bus, or temporary directory remains after each run.
  - Run `make check` and `git diff --check`.
- Completion criteria: semantic GTK automation passes on Ubuntu 26.04 Wayland
  without coordinate scripts or access to the developer's logged-in session.

