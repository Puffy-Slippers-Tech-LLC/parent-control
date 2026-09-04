# Task 28 — CI, release acceptance, and operator handoff

Execute 28A, 28B, and 28C separately. Gate implementation, acceptance judgment,
and documentation use different model budgets.

## Task 28A

- Title: Install CI jobs and the serial release command.
- Depends on: Task 27C.
- Complexity: medium. Stable suite and artifact contracts make this bounded CI
  wiring; the semantic acceptance audit belongs to 28B.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Add pre-commit/local, pull-request, nightly, updates-canary, and release jobs.
     Run host-safe unit/contracts on changes; components, package build, and
     installed-system tests on pull requests; full graphical scenarios nightly
     and for releases.
  2. Use one pinned supported Ubuntu/package lane for release and a separate
     current-security-updates canary. Canary results cannot rewrite the matrix.
  3. Serialize the VM worker. Preserve future independent workers through
     immutable baselines and disposable overlays; never share mutable guests.
  4. Always upload the validated Task 27 manifest/evidence, including failure and
     interruption. Add `make check-release VM_IMAGE=<explicit-path>` combining
     required suites and final-mode validation with fail-closed status handling.
  5. Keep ordinary staged `make check` usable; only release acceptance requires
     final traceability mode. Record exact commands and prerequisites for 28B.
- Verification:
  - Validate CI configuration and test orchestration with pass, fail, missing
    evidence, skip/xfail, first-fail/second-pass, and interrupted runner results.
  - Verify worker serialization and evidence upload on failure.
  - Run `make check` and `git diff --check`. Full release acceptance is 28B.
- Completion criteria: CI and the release command enforce the existing suite
  contracts and preserve every failure; no release acceptance is claimed yet.

## Task 28B

- Title: Audit executable traceability and pass the release gate.
- Depends on: Task 28A.
- Complexity: high. Semantic coverage and evidence across the whole specification
  require judgment beyond a syntactically valid manifest.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Audit every specification ID against executed behavior and collected
     evidence. Remove source-only acceptance claims; retain useful contracts.
     Close actual coverage gaps rather than declaring unsupported coverage.
  2. Run final-mode validation rejecting planned, missing, nonexistent, skipped,
     and expected-failing release mappings. Ensure flaky or failed evidence
     also prevents release even when a later attempt passes.
  3. Run the full `make check-release VM_IMAGE=<verified-baseline>` from a clean
     baseline with the exact release package and preserve the complete artifact
     set. Do not substitute migration/activation test packages for that artifact.
  4. Record digests, source revision, supported matrix, resource measurements,
     commands, and final results for 28C's runbook. Diagnose failures and fix
     their root causes before accepting the release.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated release tests.
  - Run `python3 tools/verify_test_traceability.py --mode final`.
  - Run the full release command and confirm zero skipped, expected-failing,
    missing, flaky, or failed requirements.
  - Run `make check` and `git diff --check`.
- Completion criteria: every applicable requirement has passing executable
  evidence from a complete release run and the gate rejects incomplete results.

## Task 28C

- Title: Finish the operator runbook and evidence index.
- Depends on: Task 28B.
- Complexity: low. This documents verified commands and recorded results without
  changing execution, requirements, coverage decisions, or release policy.
- Recommended Codex model: `gpt-5.6-luna`
- Recommended reasoning effort: `low`
- Work:
  1. Document operator prerequisites, exact suite commands, measured resource
     use, recovery steps, canary interpretation, and artifact inspection using
     28A/28B's verified outputs.
  2. Link the release evidence index, source/package/baseline digests, and final
     traceability result without copying secrets or private guest state.
  3. Check links, paths, command-help examples, and consistency between entry
     point, integration README, and release instructions.
- Verification:
  - Validate local links and documented command help without VM mutation.
  - Run `make check` and `git diff --check`; do not repeat the full release run
    for documentation-only changes.
- Completion criteria: an operator can reproduce and interpret the accepted
  release workflow from the documented commands and preserved evidence.
