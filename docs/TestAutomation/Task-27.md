# Task 27 — Artifacts, redaction, timeouts, and flake controls

Execute 27A, 27B, and 27C separately. Existing runners must continue to emit
PII-safe evidence while the common format is completed.

Apply [E2E-Coverage.md](E2E-Coverage.md). Evidence must distinguish complete
customer journeys, real fault/environment interventions, and supporting local
tests; a mocked component result or restored VM checkpoint cannot fulfill a
customer scenario. File-level traceability alone is not proof of execution.

## Task 27A

- Title: Define and enforce the shared evidence and redaction contract.
- Depends on: Task 26C.
- Complexity: high. Secret exclusion, archive safety, and evidence integrity
  require careful handling across text, structured fields, images, and video.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Define a versioned run manifest with run/suite/test/scenario/variant/step
     and requirement IDs, source revision and content digest including local
     changes, package and baseline digests, package matrix, boot/session IDs,
     timezone, tool versions, start/end times, and result. Record preconditions,
     customer actions, declared interventions, observations, and outer baseline
     operations. Prove continuity across real steps and declared reboots;
     reject checkpoint-resumed customer evidence. Define explicit
     non-applicable fields for host-only runs; never fabricate identities.
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
  6. Define and implement reconciliation of the expected suite/scenario/variant
     inventory with collection, executed assertions, and current-run evidence.
     Include non-pytest and harness/static results. A passing file or requirement
     label cannot hide a missing case, wrong required layer, partial journey,
     failed unrelated regression, stale artifact, or a missing combination.
     All required outcomes and evidence must pass; omission is not success.
     Distinguish recurring regression cases from one-time provisioning and
     explicit repeated qualification procedures. Setup tasks and historical
     acceptance repetitions are not executable daily suite entries; their
     underlying safety and behavior regressions remain required.
- Verification:
  - Run manifest, redaction/canary, safe-extraction, and malformed-archive tests.
  - Produce passing and intentionally failing reference-runner evidence and
    verify export rejects unsafe artifacts.
  - Verify rejection of omitted variants/steps, uncollected cases, incomplete
    journeys, wrong source/package/run identities, in-journey restores, and
    component/fault evidence substituted for customer acceptance.
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
     and collector, reusing the reference adapter. Include static, JavaScript,
     fixture/reproducibility, and cleanup-safety results in the suite inventory;
     they are not optional merely because no product requirement names them.
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
    smokes ten consecutive complete attempts each, using fresh local processes
    and outer baseline preparation for the existing VM. Never resume a
    scenario from a saved VM checkpoint or retry an assertion into a pass.
    Ten-run qualification is explicit maintenance for this harness change,
    not a default repeat count inherited by `test-fast`, `test-e2e` or `test-all`.
  - Run `make check`, affected component/system/E2E suites, and
    `git diff --check`.
- Completion criteria: waits are bounded and diagnosable, smoke evidence is
  stable, and no failed attempt can become a passing release result.
