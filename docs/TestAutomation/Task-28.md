### Task 28 — Install CI and release gates and close the traceability matrix

- Complexity: medium-high. This assembles completed layers into enforceable,
  resource-aware gates.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `high`
- Objective: make the complete specification the release criterion and keep
  feedback proportional to test cost.
- Work:
  1. Define pre-commit/local, pull-request, nightly, updates-canary, and release
     jobs using the stable suite interfaces from this plan.
  2. Run host-safe unit and contract tests on every change. Run hermetic component
     tests and package build on every pull request. Run installed-system tests on
     the protected VM worker for every pull request. Run all graphical scenarios
     nightly and for releases.
  3. Keep one pinned supported Ubuntu/package-matrix lane as the release gate and
     one current-security-updates lane as a canary. Never silently rewrite the
     supported matrix from canary results.
  4. Serialize jobs on a single VM worker. Preserve the design for later parallel
     workers through independent immutable overlays rather than shared mutable
     snapshots.
  5. Make CI always upload the Task 27 artifact manifest and redacted evidence.
  6. Switch the traceability validator to final mode: reject every `planned`,
     skipped, expected-failing, missing, or nonexistent release mapping.
  7. Audit every specification ID against executable evidence. Remove obsolete
     source-only acceptance claims and retain useful source checks as contracts.
  8. Add `make check-release VM_IMAGE=...` and document operator prerequisites,
     estimated resource use, exact commands, recovery, and result interpretation.
  9. Execute the complete release command from a clean baseline and preserve its
     final artifact set.
- Verification:
  - Run CI configuration validation.
  - Run the traceability validator in final mode.
  - Run `make check-release` from a clean Ubuntu baseline.
  - Confirm zero skipped or expected-failing release requirements.
  - Run `make check` and `git diff --check`.
- Completion criteria: every applicable statement in `Specification.md` maps to
  passing executable evidence, and the release command fails closed on any
  missing, skipped, flaky, or failed requirement.

