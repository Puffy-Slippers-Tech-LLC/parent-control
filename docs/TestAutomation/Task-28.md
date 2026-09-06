# Task 28 — CI, release acceptance, and operator handoff

Execute 28A, 28B, and 28C separately. Gate implementation, acceptance judgment,
and documentation use different model budgets.

Use the four-command contract in the [daily guide](../Test-Automation.md#daily-commands)
and the mandatory [real E2E coverage contract](E2E-Coverage.md). This is final
acceptance of all enumerated journeys and required variants, not just the
example journey or a collection of separately passing component screens.

## Task 28A

- Title: Implement the four test commands, CI, and the comprehensive gate.
- Depends on: Task 27C.
- Complexity: high. Inventory/selector dispatch, artifact consistency, guarded
  orchestration, and failure propagation must agree locally and in CI. Reuse
  established runners and Task 27 evidence; the semantic audit belongs to 28B.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Work:
  1. Implement `make test-fast`, `make test-system`, `make test-e2e`, and
     `make test-all` over one authoritative suite inventory and shared runner
     dispatch. Combine static, unit/property/contracts, private-D-Bus, GTK,
     child JS/GJS, and nested-Shell checks in `test-fast`. Route non-VM UI
     through `tools/run-ui-tests`; run safety prerequisites in isolation.
  2. Provide documented `COMPONENT`/`TYPE` local selectors, `AREA` system
     selectors, and `SCENARIO` E2E selection, including variants and both
     request surfaces where shared code is involved. `LIST=1` lists scope,
     prerequisites, VM use, and available choices without executing tests.
     Unknown or unexpectedly empty selections fail. `test-all` refuses
     narrowing selectors; selected runs are reported as partial coverage.
  3. Make `test-system` and `test-e2e` build/verify their inputs when invoked
     without operator-supplied artifacts. Make `test-all` validate prepared
     tooling/credentials/baseline, capture one set of source inputs including
     uncommitted changes, run host checks against those inputs, build/compare
     reproducible package/fixture outputs, and use one verified release artifact
     throughout ordinary installed and customer scenarios. Detect or prevent
     source changes mixing results; identify supplemental fixture packages.
     No intermediate operator command is needed after one-time preparation.
  4. Serialize the existing VM across layers and invocations, including
     `make -j`. Reuse its validated lease, retained product-free baseline,
     share-detachment and restoration guards. Reset only outside whole
     attempts; never create a new VM/overlay/snapshot or restore between
     customer steps. Run all enumerated scenarios and required variants,
     including real gameplay, lifecycle, fault/recovery, and environment cases
     in their declared layers. Deduplicate overlapping suite selections.
     Run each required case/variant once per ordinary attempt. Exclude completed
     setup/capture tasks and historical three-run/ten-run qualification loops
     from daily dispatch; retain their underlying regression/safety cases.
  5. Aggregate Task 27 evidence and final-mode requirement/actual-execution
     validation. Preserve and export safe partial evidence on failure or
     interruption. Missing tests/steps/evidence, required skip/xfail, stale
     artifacts, first-fail/second-pass, and cleanup failure prevent success.
     Show separate product, infrastructure, collection, and cleanup outcomes;
     unavailable required evidence never becomes a passing absence reason.
  6. Add pre-commit/local, pull-request, nightly, updates-canary, and release
     jobs using the same dispatch and acceptance contracts. Use focused local
     selections for immediate feedback; run the complete local, build, and
     installed suites on pull requests, and full graphical/all runs nightly
     and for releases. A focused CI job cannot claim a complete release pass.
  7. Use the pinned supported matrix for default `test-all`. Run a separately
     labeled current-security-updates canary with recorded actual dependency
     versions; it cannot silently change the release matrix or its baseline.
     Always upload validated available evidence, including failure results.
  8. Keep current focused `check-*` interfaces and staged `make check` usable.
     If `check-release` remains, make it an alias of the same `test-all` gate,
     without `VM_IMAGE`. Record exact commands, selectors, prerequisites,
     source-input handling, and orchestration results for 28B.
- Verification:
  - Validate CI configuration and test orchestration with pass, fail, missing
    evidence, skip/xfail, first-fail/second-pass, and interrupted runner results.
  - Verify every selector and shared dependency, `LIST=1` performs no test/VM
    operation, unknown/empty selections fail, and narrowing `test-all` fails.
  - Verify omitted suites/variants/steps, stale source/package evidence,
    source edits during a run, invalid prerequisite state, cleanup failure,
    and component evidence substituted for E2E cannot produce success.
  - Verify worker serialization under concurrent/parallel Make invocation,
    refusal of intermediate checkpoints, and evidence upload on failure.
  - Verify daily commands never install host tooling, prepare accounts, capture
    a baseline or repeat completed qualification loops. Invalid prerequisites
    fail with a diagnostic instead of triggering one-time setup implicitly.
  - Run `make check` and `git diff --check`. Full release acceptance is 28B.
- Completion criteria: the four documented commands dispatch complete or
  explicitly selected scopes through existing runners and enforce execution
  and evidence contracts. CI uses the same implementation; no release
  acceptance is claimed until 28B runs and audits the full workflow.

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
     Audit all customer scenario families and their variant matrix against
     architecture and lifecycle contracts too. Check actual ordered graphical
     operations, real authentication/gameplay/elapsed time/reboots, continuity,
     other-user isolation, and declared fault categories. No mock, backend
     shortcut, VM checkpoint, or separately passing fragment proves a journey.
  2. Run final-mode validation rejecting planned, missing, nonexistent, skipped,
     and expected-failing release mappings. Ensure flaky or failed evidence
     also prevents release even when a later attempt passes.
  3. Run `make test-all` from the prepared development/VM host with no manual
     intermediate commands. Use the retained product-free baseline only
     outside independent attempts. Preserve the complete evidence set for the
     exact source inputs/release artifact; supplemental migration/activation
     packages cannot replace it. Verify expected-versus-executed inventories,
     not only file existence or a `covered` label in requirements.json.
  4. Record digests, source revision, supported matrix, resource measurements,
     commands, and final results for 28C's runbook. Diagnose failures and fix
     their root causes before accepting the release.
- Verification:
  - Run cleanup-safety regressions in isolation before integrated release tests.
  - Run `python3 tools/verify_test_traceability.py --mode final`.
  - Run the full release command and confirm zero skipped, expected-failing,
    missing, flaky, or failed required tests, scenarios, variants, and
    requirements, with complete cleanup and valid current-run evidence.
  - Review intentionally failed orchestration evidence proving unavailable
    VM/prerequisites, omitted tests, stale artifacts, interrupted journeys,
    intermediate restore requests, and cleanup failure cannot produce green.
  - Run `make check` and `git diff --check`.
- Completion criteria: every applicable requirement and enumerated required
  journey/variant has passing evidence from a complete real run. Harness and
  static regressions also pass; the gate rejects incomplete or simulated
  acceptance. Record any documented scope limits without promising that
  automation proves the absence of every possible regression.

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
     Lead with the four daily commands and focused selector examples. Measure
     the full `test-fast` runtime including GTK/nested-Shell tests; describe
     it as local feedback, not a guarantee of seconds. Explain one-time setup,
     actual VM mutations, real-duration waits, and outer-only baseline resets.
  2. Link the release evidence index, source/package/baseline digests, and final
     traceability result without copying secrets or private guest state.
  3. Check links, paths, command-help examples, and consistency between entry
     point, integration README, and release instructions.
- Verification:
  - Validate local links and documented command help without VM mutation.
  - Run link/reference checks and `git diff --check`; do not rerun product,
    component, VM or full release tests for documentation-only changes.
- Completion criteria: an operator can reproduce and interpret the accepted
  release workflow from the documented commands and preserved evidence.
