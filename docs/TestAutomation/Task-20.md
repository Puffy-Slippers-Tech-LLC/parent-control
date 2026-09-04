### Task 20 — Automate clean installation, reboot, and startup readiness

- Depends on: Task 19B.
- Complexity: high. This is the first complete release-path graphical job.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Model rationale: retain Sol for the first complete graphical package journey;
  the guarded worker and install assertions are already implemented, while
  startup failure diagnosis still spans several services.
- Objective: prove a clean supported Ubuntu machine reaches a safe login screen
  after installing the exact release artifact.
- Work:
  1. Start from the before-product baseline and upload the exact `.deb`, fixture
     bundle, and their digests through the controlled asset channel.
  2. Verify the product is absent, install the package through its real package
     path, record output, and verify the product-created reboot marker.
  3. Reboot through os-autoinst power and console APIs.
  4. Assert visually that GDM becomes usable only after fapolicyd readiness.
     Independently prove the broker publishes its D-Bus object only after its
     startup reconciliation completes, as specified in `System-Design.md`.
  5. Assert through serial that installed files, ownership, services, D-Bus,
     Polkit, PAM, session descriptors, configuration, extension payload, logs,
     and execution policy match the package.
  6. Prove a broker startup reconciliation failure prevents broker readiness and
     a fapolicyd readiness failure prevents managed graphical login startup.
  7. Collect all startup evidence and update installation/startup requirement
     mappings.
- Verification:
  - Run runner cleanup-safety regressions in isolation before live scenarios.
  - Run the clean-install scenario twice from separate fresh overlays.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<clean-install>`,
    package-focused system tests, `make check`, and `git diff --check`.
- Completion criteria: a digest-identified release package passes a real clean
  installation and reboot with visible and backend readiness evidence.
