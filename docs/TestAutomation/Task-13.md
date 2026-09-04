# Task 13 — Debian-package autopkgtest infrastructure

Task 12 supplies an immutable, product-free baseline and provenance, not a
disposable-guest runner. Execute 13A and 13B separately in checklist order.

## Task 13A

- Title: Build reproducible package and fixture artifacts.
- Depends on: Task 12C.
- Complexity: medium. This extends the existing package build without VM control.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Add a reproducible build command producing a named `.deb`, its SHA-256,
     source revision, build inputs, and package/tool versions. Never install it
     on the development host.
  2. Reuse Task 11's fixture builder; record the fixture bundle digest beside the
     package digest. Define the artifact paths and manifest consumed by 13B.
  3. Document build prerequisites and commands; add any development dependencies
     to `setup.sh` and the pinned test-tool list.
- Verification:
  - Build twice from the same recorded inputs; compare package contents,
    metadata, and digests, explaining and removing uncontrolled variation.
  - Run focused build/manifest tests, `make check`, and `git diff --check`.
- Completion criteria: repeatable, digest-identified artifacts and a documented
  manifest are available for 13B without installing the product.

## Task 13B

- Title: Add the guarded autopkgtest QEMU runner and install smoke.
- Depends on: Task 13A.
- Complexity: very high. New guest ownership, immutable storage, package
  installation, reboot, and interruption cleanup must work together.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Add `debian/tests/control` and test executables with the required
     `isolation-machine`, root, and reboot capabilities. Use public autopkgtest
     interfaces and pin development tools through `setup.sh`.
  2. Own disposable-guest creation here: validate the Task 12 baseline digest,
     provenance, ownership, mode, and independent QCOW2 format; let
     `autopkgtest-virt-qemu` create a fresh disposable testbed through its
     supported interface. Never boot the source domain or write its baseline.
  3. Build a minimal testbed configuration that exposes no writable host
     filesystem, including the source domain's `/Data` share. Use the runner's
     supported asset transfer, fresh guest identity, and explicit guest guard.
  4. Implement `make check-system VM_IMAGE=<explicit-path>`, bounded readiness,
     reboot, artifact retrieval, and interruption cleanup. Record ownership of
     each spawned process and created file; test refusal, identity replacement,
     timeout, and interruption before any live run.
  5. Install the exact 13A artifact through the real package path and reboot
     through autopkgtest. Assert package status, installed ownership/modes,
     service readiness, D-Bus activation, PAM registration, Polkit files, session
     descriptors, generated execution rules, and reboot markers.
  6. Export xUnit/TAP results and package/baseline digests through the existing
     redacted collector. Document the runner contract for later system tests
     and the baseline/asset guards reusable by Task 19.
- Verification:
  - Run runner cleanup-safety regressions in isolation, then host-safe guard,
    interruption, and refusal tests.
  - Run clean install/reboot tests on fresh disposable testbeds; verify the
    baseline digest, source domain, and development host remain unchanged.
  - Run `make check-system VM_IMAGE=<verified-baseline>`, `make check`, and
    `git diff --check`.
- Completion criteria: real package lifecycle tests pass in guarded disposable
  guests, with reproducible evidence and no mutation of the baseline or host.
