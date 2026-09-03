### Task 27 — Complete artifact, redaction, timeout, and flake controls

- Complexity: medium-high. Evidence from three runners must use one secure,
  diagnosable format.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: make failures actionable without leaking credentials or accepting
  flaky passes.
- Work:
  1. Define one run manifest for unit, component, system, and E2E results with run
     ID, test ID, requirement IDs, source revision, package digest, baseline
     digest, package matrix, boot ID, timezone, tool versions, start/end times,
     and result.
  2. Collect JUnit/TAP, coverage, screenshots, os-autoinst video, serial logs,
     service status, relevant journals, D-Bus replies, PAM results, session state,
     source and compiled fapolicyd rules, process evidence, and product logs.
  3. Extend redaction tests for openQA variables, password-like fields, SSH keys,
     bearer values, Polkit text, screenshots, archive names, and manifest fields.
  4. Never alter source logs. Redact only copied artifacts and retain checksums of
     the redacted archive.
  5. Standardize bounded waits and diagnostic messages for boot, SSH, D-Bus,
     service readiness, screen needles, app start/exit, lock, and logout.
  6. Add a whole-scenario rerun command that records both attempts and preserves
     the original failure. Never convert a failed-then-passed release result to a
     pass.
  7. Run selected stable component and E2E scenarios repeatedly to identify and
     fix synchronization races at their root causes.
- Verification:
  - Generate passing and intentionally failing artifacts from every runner.
  - Run automated secret scans and safe-archive extraction tests.
  - Run stable smoke scenarios ten consecutive times.
  - Run `make check`, relevant component/system/E2E tests, and
    `git diff --check`.
- Completion criteria: every failure produces complete PII-safe evidence and no
  assertion depends on an unexplained delay or retry-to-pass behavior.

