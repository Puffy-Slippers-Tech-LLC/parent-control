# Task 13 — Debian-package system-test infrastructure

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

- Title: Add the guarded pytest system runner and install smoke.
- Depends on: Task 13A.
- Remaining complexity: medium. The runner and safety regressions exist;
  remaining work is bounded install/reboot acceptance and final verification.
- Recommended Codex model for remaining work: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- User-approved revision — 2026-09-04: replace autopkgtest with pytest for
  installed-package tests. Stock autopkgtest 5.55's guest descriptor scans and
  host descendant-discovery cleanup conflict with the explicit process-ownership
  rule; neither private patches nor exceptions to that rule are allowed.
- Work:
  1. Add guest pytest install/reboot tests, excluded from default host collection,
     and fail-closed guest guards. Pin guest test-tool bootstrap through the
     runner and document development dependencies in `setup.sh`.
  2. Serialize access to the existing `ubuntu26.04` libvirt/QEMU VM using Task
     12's lock. Validate the private finalized provenance, snapshot identity,
     disk-chain identity and immutable backing digests, then restore the retained
     internal baseline. Never create a replacement VM, copy, or overlay, or
     replace/delete the named snapshot.
  3. Remove the preparation-only `/Data` share and other host-sharing channels
     before test boot. Use supported libguestfs bootstrap and SSH asset transfer,
     a fresh run identity, a pinned SSH host key, and an explicit guest guard.
  4. Implement `make check-system ARTIFACT_DIR=<13A-output>` with bounded
     readiness, reboot, evidence retrieval, and interruption cleanup. Track each
     spawned process with a pidfd and bind VM cleanup to the recorded instance.
     Test refusal, identity replacement, timeout, and interruption before a live run.
  5. Install the exact 13A artifact through APT in the guest, execute pytest
     checks before and after an actual reboot, and assert package status/content,
     installed ownership/modes, service readiness, D-Bus activation, PAM
     registration, Polkit files, session descriptors, generated/loaded execution
     rules, and reboot markers. No host product installation is permitted.
  6. Export pytest xUnit, an aggregate xUnit/TAP result, and package/fixture/
     baseline provenance digests using the existing redaction helper. Document
     the lease, transfer, phase and evidence contracts for subsequent system
     tasks and the VM guards reusable by Task 19.
- Verification:
  - Run runner cleanup-safety regressions in isolation, then focused host-safe
    guard, transport, installation-gate, interruption and refusal tests.
  - Run clean install/reboot tests from the restored baseline. Reverify snapshot
    metadata, backing digests and product-free offline inspection after cleanup;
    restore prior persistent domain XML and leave the VM off.
  - Verify the development host's product and PAM integration fingerprints remain
    unchanged, including after a failed attempt.
  - Run `make check-system ARTIFACT_DIR=<verified-13A-output>`, `make check`,
    and `git diff --check`. Do not retry failed assertions or count skips as passes.
- Completion criteria: real installed-package lifecycle checks pass inside the
  guarded existing VM, with digest-identified evidence, preserved baseline,
  restored domain configuration, and no product installation on the host.

### Accepted handoff — Task 13B completed 2026-09-04

The full guarded install/reboot run passed. Do not redo Task 13B; Task 14 owns
installed broker identity and authorization coverage. See the
[master completion record](Test-Automation.md#task-13b-completed--2026-09-04)
for verification commands, digests and evidence.

- Accepted input: `/tmp/onpc-task13b-acceptance-ndbI8L/input/`.
- Accepted evidence: `/tmp/onpc-system-g33ljzev/evidence/`; both guest xUnit
  phases contain two passing cases with zero failures, errors or skips.
  Aggregate outcome is `passed`, category `all-checks-passed`, and
  `cleanup_phase=complete`.
- Cleanup verified the retained snapshot, immutable backing digests,
  product-free offline inspection and unchanged host product/PAM fingerprints;
  restored the prior persistent domain XML; and left the VM shut off.
- Both Makefile and direct runner entry points prevent Python bytecode writes.
  The generated cache is readable and owned by the developer; common checks
  completed without the old permission warning.
- The corrected SSH readiness path and pre-reboot evidence checkpoint passed
  live acceptance. The guest also waits for systemd boot completion before
  installed-system assertions; all required service assertions still apply.
- Preserve prior failed evidence, including
  `/tmp/onpc-system-5rul064t/evidence/`; this successful corrected-code run
  does not change earlier attempts into passes.
- Reuse the lease, transport, guest guard and evidence contracts documented in
  `tests/integration/README.md`. No product/runtime change or data migration
  was needed; test-only integration has activation class `none`.
- Remaining-work review selected Terra/medium because implementation and
  safety regressions already existed. The user authorized continuation in this
  session; the session's developer-provided identity is GPT-6, with exact
  deployment variant and reasoning setting unavailable. No model benchmark
  or claimed Terra execution is implied.
