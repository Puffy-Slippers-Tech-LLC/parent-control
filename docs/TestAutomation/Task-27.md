# Task 27 — Artifacts, redaction, timeouts, and flake controls

Execute 27A, 27B, and 27C separately. Existing runners must continue to emit
PII-safe evidence while the common format is completed.

## Task 27A

- Title: Define and enforce the shared evidence and redaction contract.
- Depends on: Task 26B.
- Complexity: high. Secret exclusion, archive safety, and evidence integrity
  require careful handling across text, structured fields, images, and video.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Define a versioned run manifest with run/test/requirement IDs, source
     revision, package and baseline digests, package matrix, boot ID, timezone,
     tool versions, start/end times, and result. Define explicit non-applicable
     fields for host-only runs; never fabricate a package or boot identity.
  2. Implement shared validation, copied-artifact redaction, safe archive
     construction/extraction, and redacted-archive checksums. Never alter logs.
  3. Test secret-like fields, SSH keys, bearer values, Polkit text, os-autoinst
     variables, filenames, and manifest fields. Cover screenshot/video capture
     boundaries and synthetic canaries; text substitution alone cannot sanitize
     visual evidence. Fail export closed on unsafe artifacts.
  4. Specify adapters for JUnit/TAP, coverage, screenshots/video, serial logs,
     service/journal/product logs, D-Bus/PAM replies, sessions, source/compiled
     rules, and process evidence. Implement one reference runner adapter.
  5. Document the exact schema, artifact allowlist, redaction API, and adapter
     examples so 27B only wires established interfaces.
- Verification:
  - Run manifest, redaction/canary, safe-extraction, and malformed-archive tests.
  - Produce passing and intentionally failing reference-runner evidence and
    verify export rejects unsafe artifacts.
  - Run `make check` and `git diff --check`.
- Completion criteria: an executable evidence/privacy contract and reference
  adapter are ready for mechanical runner integration.

## Task 27B

- Title: Wire the remaining runners to the evidence contract.
- Depends on: Task 27A.
- Complexity: low. Field mappings and collector interfaces are fixed by 27A;
  this task adds adapters rather than changing privacy or archive policy.
- Recommended Codex model: `gpt-5.6-luna`
- Recommended reasoning effort: `medium`
- Work:
  1. Connect unit, component, installed-system, and E2E outputs to 27A's schema
     and collector, reusing the reference adapter.
  2. Include all applicable evidence categories listed by 27A, record explicit
     absence reasons, and retain the original result on collection failure.
  3. Add focused adapter contract tests and document artifact locations and
     inspection commands. Do not weaken validation to make an adapter pass.
- Verification:
  - Generate passing and intentionally failing artifacts from every runner.
  - Run the shared secret scans, manifest validation, and safe extraction
    checks on each exported archive.
  - Run required cleanup-safety regressions before integrated samples,
    `make check`, and `git diff --check`.
- Completion criteria: every runner emits complete, validated, PII-safe evidence
  through the same contract.

## Task 27C

- Title: Finish bounded waits and flake classification.
- Depends on: Task 27B.
- Complexity: high. Existing workflows must be diagnosed for synchronization
  races without weakening assertions or retrying failures into passes.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Work:
  1. Standardize bounded waits and diagnostic categories for boot, SSH, D-Bus,
     service readiness, needles, app start/exit, lock, and logout.
  2. Add a whole-scenario rerun command recording both attempts and preserving
     the original failure. Failed-then-passed must still fail a release.
  3. Repeatedly run selected stable component/E2E smoke cases, diagnose actual
     races, and fix root causes without unexplained sleeps or assertion retries.
     Use the evidence contract to distinguish product and infrastructure failure.
- Verification:
  - Test timeout, collection, and rerun result propagation, including first-fail/
    second-pass and interrupted attempts.
  - Run cleanup-safety regressions in isolation, then stable component and E2E
    smokes ten consecutive times each, using fresh processes/overlays.
  - Run `make check`, affected component/system/E2E suites, and
    `git diff --check`.
- Completion criteria: waits are bounded and diagnosable, smoke evidence is
  stable, and no failed attempt can become a passing release result.
