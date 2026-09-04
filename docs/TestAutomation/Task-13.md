### Task 13 — Add Debian-package autopkgtest infrastructure

- Complexity: high. Package installation, reboot capability, and testbed cleanup
  must align with Debian and Ubuntu conventions.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: test the installed binary package and system integration separately
  from graphical user journeys.
- Work:
  1. Add a reproducible package-build command that produces a named `.deb` and
     SHA-256 record without installing it on the host.
  2. Add `debian/tests/control` and test executables using the required
     `isolation-machine`, root, and reboot capabilities.
  3. Configure `autopkgtest-virt-qemu` to consume only the Task 12 disposable
     baseline and overlay mechanism.
  4. Install the exact built package, reboot through autopkgtest, and verify
     package status, installed file ownership and modes, service readiness,
     D-Bus activation, PAM registration, Polkit files, session descriptors,
     generated execution rules, and reboot marker behavior.
  5. Run clean package-install tests using a fresh overlay. Never assemble
     product files manually.
  6. Export xUnit/TAP results and guest artifacts through the existing redacted
     collector.
  7. Add the guarded `make check-system VM_IMAGE=...` entry point.
- Verification:
  - Run package build twice and compare package contents and recorded inputs.
  - Run clean package-install tests on fresh overlays.
  - Run `make check` and `git diff --check`.
- Completion criteria: installed-system tests exercise the real package lifecycle
  and leave the baseline and host unchanged.
