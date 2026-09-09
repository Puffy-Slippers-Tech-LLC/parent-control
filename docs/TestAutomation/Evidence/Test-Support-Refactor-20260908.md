# Finished test infrastructure refactor

User-directed scope: review the implemented test layers, consolidate reusable
infrastructure, update maintenance documentation and pass existing tests.
Acceptance completed on 2026-09-08. This took precedence over backlog
implementation for this change. Task 20 remains the next backlog task; pending
scenarios and later Task 15A work retain their existing status.

## Review and resulting structure

| Reviewed layer | Result |
| --- | --- |
| Unit, property and contract cases | Shared broker/configuration doubles, package machines, script imports, VM fixtures, E2E evidence/provenance/credentials and Perl probes now live in `tests/support`. Normal imports use one pytest path configuration. Independent state-machine oracles and scenario-specific fault injection remain in cases. |
| Private D-Bus components | Extracted the actual Gio harness and recording adapters. Each acquired connection/service is registered for cleanup immediately, including partial setup failures. |
| GTK previews and shared child/kiosk form | Shared owned-process lifecycle and complete JSON-lines event reading. Form unit tests bind actual class methods instead of rewriting their AST. Parent/child/kiosk scenarios keep their existing assertions. |
| Child Node/GJS and nested Shell | Shared fresh Node context for indicator tests. GJS already uses its existing focused runner. Shell input now has one delivery lifecycle; diagnostics include pointer placement on failure. |
| Installed package, authorization and enforcement | Existing guarded runner/lease/transport remain the infrastructure boundary. Real-caller reply validation, account snapshots and guarded disposable identities are shared guest helpers and included in selected staging/provenance. |
| Graphical E2E and qualifications | Existing credential, input, recorder, evidence and cleanup libraries remain authoritative. Host fixtures no longer import collected case modules. E2E-001 remains the canonical executable harness smoke; 156 pending variants are not implemented by this refactor. |

The [support guide](../../../tests/support/README.md) is the entry point for
future work. It maps each solved problem to its helper and records isolation,
privacy, ownership and staging requirements. The daily guide, layer guides and
[reuse map](../Reuse-Map.md) link to it. Architecture regressions prevent
test-to-test imports and module-level `sys.path` bootstrapping from returning.

Tests retain scenario names, parameter identities, negative cases and independent
expectations. Standard pytest/unittest/Hypothesis facilities remain in use;
simple local assertions and one-off scenario state are not hidden behind a new
test language. No product code, saved data, setup policy or baseline is changed.
Test helpers activate on the next invocation.

## Faults found during refactoring

- PTY capture previously waited for process exit before draining output. The
  shared reader drains concurrently, applies a deadline, and reaps only its
  owned child. A real large-output regression exercises pipe and PTY modes.
- Preview and D-Bus setup could fail before fixture teardown was registered.
  Their shared lifecycles now clean acquired resources on partial setup and
  attempt remaining cleanup even when one cleanup operation fails.
- Full installed selection refused identical shared helper declarations before
  VM mutation (`selection:duplicate-input-target`). Staging now coalesces exact
  source/target pairs while rejecting conflicting sources before any copy. A
  regression reproduced the original refusal and covers both boundaries.
- The full UI run exposed an intermittent first right-click loss in nested
  Shell. Initial evidence is retained in `artifacts/ui/child-shell/interaction/`
  under `onpc-child-interaction-6dj4900g`, `onpc-child-interaction-gksc_x31` and
  `onpc-child-interaction-kz07vxrs`. Reconnecting alone did not fix it. The last
  attempt's pointer screenshot showed correct placement with no menu. The
  revised helper separates motion, press and release dispatch intervals and
  completes the input session before observing the action. Original failures
  remain failed; final verification is recorded below.

## Verification

Pre-change baseline: 4,606 unit/contract cases and 17 private-D-Bus cases passed;
526 cleanup-safety cases and three subtests passed separately.

All implemented suites below passed. Existing collected test names and
parameter identities were retained; no existing case was skipped or weakened
to obtain these results.

| Verification | Final result |
| --- | --- |
| `make check` | 4,942 unit/contract cases and 17 private-D-Bus cases passed. Traceability validation passed. |
| Isolated cleanup prerequisites | 546 cases and three subtests passed before protected operations. |
| `tools/run-ui-tests --timeout 900s tests/ui -q` | All 82 cases passed in 297.39 seconds. The corrected Shell interaction passed three consecutive runs, including this full suite. |
| `tools/run-tests child-node` | All seven cases passed. |
| `tools/run-tests child-gjs` | Passed; coverage retained at `/tmp/onpc-gjs-coverage-otgxr1ih/coverage.lcov`. |
| `make check-static` | Passed. |
| Documentation validation | 23 document/traceability regressions passed; local link and whitespace checks passed. |
| `tools/run-tests backend` | Pinned graphical backend validation passed. |
| `tools/run-tests integration check_package_notice` | All ten APT/apt-get first-install, reinstall, removal, install-after-removal and failed-trigger scenarios passed; evidence at `/var/tmp/onpc-package-notice-m2oguprf`. |
| `tools/run-tests artifacts build` | Package and fixture construction and digest verification passed. |
| Full installed runner | All 238 executions passed, with successful collection, infrastructure and cleanup. |
| Canonical E2E-001 runner | Passed, including all nine observations, terminal evidence validation and cleanup. |

Passing Shell interaction artifacts are retained under
`artifacts/ui/child-shell/interaction/` in `onpc-child-interaction-z3f4_euc`,
`onpc-child-interaction-52q_a0pz` and `onpc-child-interaction-y2mhw4ks`.

## Guarded installed and graphical evidence

Both live runners used `/tmp/onpc-test-artifacts-sf_4_o28` with these identities:

- Source: `37d4b4170d02852408e8df57185f436704dd56a67e58e8bb2a183328aa2a9929`.
- Package: `81f4790120273529ed65a2371728daf490540450e5bd647c66c0aa5d71ca743b`.
- Fixture payload: `1b2aee47186c5057c581a6777c64f1ed7b40e960f47cc4e676e5628753074365`.

The installed command was `tools/run-tests system --artifacts
/tmp/onpc-test-artifacts-sf_4_o28`. Its result is retained at
`/tmp/onpc-system-z348mlkt/evidence/result.json`, with JUnit and TAP alongside it.
The full selection executed two installed, two rebooted, 229 authorization and
five enforcement cases. All four outcome domains passed and `cleanup_phase`
is `complete`. This also supplies installed runtime evidence for the five
already implemented native Task 15A cases; it does not complete that task's
remaining application/route coverage.

The graphical command was `tools/run-tests e2e --artifacts
/tmp/onpc-test-artifacts-sf_4_o28 --scenario E2E-001`. The invocation evidence is
`/tmp/onpc-e2e-evidence-8jd5vqif`, scenario evidence is
`/tmp/onpc-e2e-evidence-d008pbd8`, and private raw worker evidence is
`/tmp/onpc-graphical-smoke-z2imivse`. The terminal result and every outcome domain
passed, with no first failure and lease phase `complete`. The initial and
returned public GDM screenshots (`smoke-1.png` and `smoke-16.png`) were visually
reviewed through the approved export helper. Raw screenshots, credentials and
terminal output remain outside this document. E2E-001 proves its declared
harness scope; it does not establish pending product/customer requirements.

Source remained frozen throughout both live runs and cleanup. Only documentation
was updated afterward to record these results. Build fresh source-bound artifacts
before any subsequent live run. Historical one-off qualification results remain
in their owning evidence records; the maintained shared paths were exercised by
the host regressions, installed suite and canonical graphical smoke above.
