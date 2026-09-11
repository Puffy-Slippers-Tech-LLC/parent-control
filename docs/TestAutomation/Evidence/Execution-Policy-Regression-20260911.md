# Established execution-policy regression pass — 2026-09-11

User-directed regression validation of the uncommitted broker notification
recovery change. Scope: established test suites only. No unfinished roadmap
task or pending E2E scenario was implemented or executed.

## Product scope

The only application behavior change in the original uncommitted work is
[`execution_policy.py`](../../../broker/oh_no_parent_control/execution_policy.py).
It retries rule notification when a new adapter or failed rollback leaves its
notification status unknown. The package activation helper also moved from
`tools/` to [`debian/package_activation.py`](../../../debian/package_activation.py),
with only its module docstring changed; Makefile installation/generation paths
follow that move. Other original changes concern tests, documentation and
development/publishing tooling.

This session made no additional product change. The package bytes remained
identical across all builds before and after the test-tool corrections below.

## Results

| Established command | Result |
| --- | --- |
| `make check` | Passed: 7,411 unit/contract tests, 58 private-D-Bus components, stage traceability, syntax and source guards. |
| `make check-static` | Passed: ShellCheck and GJS checks. |
| `tools/run-tests child-node` | 12 passed. |
| `tools/run-tests child-gjs` | Passed; retained LCOV under `/tmp/onpc-gjs-coverage-o5lav8cc/`. |
| `tools/run-ui-tests --timeout 900s tests/ui -m ui -q` | 140 passed in 849.71 seconds, including GTK and nested Shell. |
| `make check-test-fixtures` | Passed: 9 safety prerequisites and 3 fixture tests, including native/Flatpak runtime. |
| `tools/run-tests backend` | Passed; tooling readiness only. |
| Two `tools/run-tests artifacts build` runs and `artifacts compare` | Passed: fresh package/fixture inputs and reproducibility. |
| `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-e6ejhb9z` | Full scope passed: all 240 expected executions. |
| `tools/run-tests e2e --artifacts /tmp/onpc-test-artifacts-e6ejhb9z --scenario E2E-001` | Established smoke passed; exit status 0. |

The final system breakdown is 2 installation, 2 post-reboot, 229 authorization,
6 enforcement and 1 graphical session-expiry execution. All five JUnit phase
files were collected. Product, infrastructure, collection and cleanup outcomes
all passed. Native allow/deny transitions and other-child isolation passed
against installed fapolicyd 1.3.6-1.

E2E-001 completed all nine observations, including authenticated serial command,
logout and GDM return. Screen matches passed; initial and returned GDM images
were visually reviewed. Final invocation and acceptance outcomes passed, with
host/source preservation, owned-process shutdown, restored baseline and VM off
all verified. This existing smoke is harness coverage, not customer-journey
acceptance.

## Interruptions and test-tool corrections

The session crash interrupted the first system attempt after its two install
checks passed and left its recorded VM at `cleanup-requested`. The UI attempt
also lost its final result. Both interrupted runs remain incomplete, not passes.
The existing cleanup recovery supported only VNC graphical attempts. Added
[`check_system_recovery.py`](../../../tests/integration/check_system_recovery.py)
using the same exclusive lease and journal/domain/baseline checks with fixed
SPICE selection. Recovery passed and restored the VM. Focused validation passed
366 tests; isolated cleanup prerequisites passed 708 tests and 3 subtests.
The full `make check` result above includes this recovery change.

The next full system run passed 239 executions, then failed preparing the last
session check with `expiry:activation-failure-fixture-collision`. The same offline
recovery probe ran in both enforcement and graphical preparation, reusing a
directory retained for outer VM cleanup. Two repeat-execution regressions
reproduced the failure. Each invocation now creates its own private directory;
exact metadata restoration and outer cleanup ownership remain enforced.
After this final test-only correction, 150 focused checks passed, including
repeated success/failure restoration and guest-guard safety. Fresh builds,
reproducibility and the full 240-execution system rerun then passed. No product
regression was found in the established coverage.

## Retained evidence

- Source HEAD: `00492e8fef7b3a210865bab228ed6a367109c2bc`.
- Final tested source digest: `095e81acc8b10f099754139e54f8ded28b047558094851233266cb2bcae686bb`.
- Package SHA-256: `1bbf0b188f048ed5cdb62fecd044dba2ae743fbb6b15e59fe187716fc738ea62`.
- Final reproducible inputs: `/tmp/onpc-test-artifacts-e6ejhb9z` and `/tmp/onpc-test-artifacts-whpbkyko`.
- Interrupted system attempt: `/tmp/onpc-system-utm2ywqf`.
- Successful crash cleanup: `/tmp/onpc-system-recovery-jy81li36/result.json`.
- Preserved fixture failure: `/tmp/onpc-system-f7fiylpt/evidence/result.json`; exact traceback in `private/command-0143-stderr.txt` under that attempt.
- Passing full system result: `/tmp/onpc-system-06munixy/evidence/result.json`.
- Passing E2E invocation: `/tmp/onpc-e2e-evidence-jak462ca/invocation-terminal-candidate.json`, corroborated by post-close stdout and exit status 0.
- E2E acceptance: `/tmp/onpc-e2e-evidence-saqj2nws/acceptance.json`.
- Original graphical evidence: `/tmp/onpc-graphical-smoke-lzgcbkw0/testresults/`.

Read private files through the documented [artifact reader](../../../tests/README.md#prompt-free-test-artifact-access).
Original failures, logs and screenshots were preserved. No release was published
and no roadmap task was marked complete. This evidence document was written
after execution; it changes no tested source or package behavior.
