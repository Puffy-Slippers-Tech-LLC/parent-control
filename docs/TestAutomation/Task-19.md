### Task 19 — Establish the os-autoinst end-to-end test distribution

- Complexity: high. The framework owns QEMU, VNC, serial consoles, screen
  matching, secrets, and result artifacts.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: create the outside-the-VM driver required for GDM and lock-screen
  acceptance.
- Work:
  1. Add a repository-local os-autoinst test distribution under `tests/e2e` with
     `main.pm`, a small distribution class, public console definitions, scenario
     modules, needles, configuration templates, and a guarded launcher.
  2. Use Ubuntu 26.04's maintained `os-autoinst` package and the QEMU backend.
     Pin and record the worker tool versions. Do not attach to the protected
     libvirt domain and do not use the svirt root-password workflow.
  3. Use stable Perl test modules for os-autoinst orchestration. Keep complex
     backend assertions in versioned guest scripts and pytest tests.
  4. Configure a VNC graphical console plus virtio serial terminal. Use the
     graphical console only for real user actions and visible assertions; use the
     serial console for setup, state assertions, and artifact collection.
  5. Store passwords in os-autoinst secret variables and enter them with the
     secret-safe password API. Never put them in screenshots, command output, or
     vars artifacts.
  6. Use small stable screen-match regions, accessible text, explicit click
     points, and excluded dynamic areas. Never match a whole animated screen.
  7. Add one smoke scenario that boots a disposable Task 12 overlay, recognizes
     GDM, switches to serial, executes a harmless command, switches back, records
     a screenshot, and shuts down.
  8. Add the guarded `make check-e2e VM_IMAGE=... SCENARIO=...` command.
- Verification:
  - Run the smoke scenario three consecutive times from fresh overlays.
  - Review screenshots, video, serial output, secrets redaction, and overlay
    cleanup.
  - Run `make check` and `git diff --check`.
- Completion criteria: os-autoinst reliably controls boot, graphical input, and
  serial assertions without touching the protected domain or host data.

