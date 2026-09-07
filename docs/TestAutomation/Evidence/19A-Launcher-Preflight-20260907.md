# Task 19A launcher preflight — 2026-09-07

Completed the host-side launcher boundary on the development/host machine.
This is dispatch/guard regression evidence, not graphical scenario acceptance.
No VM attempt was started, so preparation/test/cleanup VM timings are not
applicable. The existing worker qualification remains applicable.

## Implemented result

- `tests/e2e/runner.py` provides host-only inventory preflight. Listings preserve
  all pending cases, selection scope, prerequisites and the exact inventory hash.
- `tools/run-tests e2e` and the installed `onpc-test-runner` use the same
  preflight before privilege checking (ordinary launcher), safety prerequisites
  or root test execution (installed dispatcher).
- `make check-e2e LIST=1 SCENARIO=...` delegates to the validated category
  launcher. Make passes selector values through environment variables instead
  of interpolating them into recipe shell commands. `VM_IMAGE` and invalid
  `LIST` values fail; listing cannot accept artifact paths.
- Pending/unknown/empty/wildcard selections, malformed or symlinked inventory
  inputs and undeclared checkpoint/resume/command options refuse execution.
  Error messages exclude raw caller values.
- A synthetic ready declaration also fails closed at
  `e2e:execution-controller-unfinished`. It cannot launch its declared code or
  use the worker's successful diagnostic report as scenario evidence.

## Verification

| Command/scope | Result |
| --- | --- |
| `tools/run-unit-tests tests/unit/test_e2e_runner.py tests/unit/test_e2e_inventory.py tests/unit/test_test_launchers.py tests/unit/test_privileged_test_runner.py -q` | 191 passed, 1.57 s; includes 33 new launcher tests |
| Focused runner authorization/launcher regression selection | 101 passed, 2.10 s |
| `make check` outside sandbox | Exit 0; 1,959 unit/contracts in 26.53 s, 17 private-D-Bus components in 0.34 s, syntax and stage traceability |
| `./setup.sh --test-tools-only` outside sandbox | Exit 0; installed dispatcher refreshed through the supported setup entry point |
| `tools/run-tests e2e --list --scenario E2E-023/fullscreen` | Exit 0; one explicitly pending case, partial scope |
| `tools/run-tests e2e --artifacts /tmp/onpc-e2e-preflight-unused --scenario E2E-001` | Expected exit 2: `run-tests: selection:pending` |
| `pkexec /usr/local/libexec/onpc-test-runner e2e --artifacts /tmp/onpc-e2e-preflight-unused --scenario E2E-001` | Expected exit 2; installed dispatcher's generic refusal; no cleanup prerequisite or selected-test start output |
| `git diff --check` | Passed |

The Make listing/refusal and recipe-shell injection checks execute the real
Make/category entry points in the unit suite. Boundary mocks assert that
privilege checks, subprocess execution and cleanup prerequisites are never
called for rejected requests. Temporary ready declarations remain in test
storage; all repository scenarios stay pending. No expensive attempt or
unresolved diagnosis was incurred. All command handles exited; no owned VM or
worker operation remains from this session.

## Verified code identities

| File | SHA-256 |
| --- | --- |
| `tests/e2e/runner.py` | `6b537e58dfd4896abfd2d97efac1b4771ac28e11cdd6ac1e07713471b805b3b2` |
| `tools/onpc-test-runner` | `a9c226eb61c8bbedb6bbb8189c40e263af4c920151ee12360e02b907280e7b7d` |
| `tools/test_commands.py` | `306d96bf3b1366451ed8795d5b5704cebd1ad17c88b6f6cd769900d23008242c` |
| `Makefile` | `ebb9aa18fef20639ca89389ee00953436b9fb143903008c7ff46128b46e85672` |
| `tests/unit/test_e2e_runner.py` | `2d204270045a4c65d960fe296c7a75f1686d9aed988b075b50cb5633d4cb2de0` |
| `tests/unit/test_test_launchers.py` | `38685b161f5599b95a4b4a7cf71878df8cfe49ae4f6517f8a61f1f57a70aa4a8` |
| `tests/e2e/scenarios.json` | `c2d2bac4bea5da49be82f41a7de3e8f9e2780fbbee9c2bad09450dda647e35d4` |
| Installed `/usr/local/libexec/onpc-test-runner` | `5ee86e2006d53d8be9ca014193406536e3f2fbe31f0c733a19cb70dc4d291e6f` |

The installed copy has setup-rendered checkout and pinned VM constants, hence
its different hash. Setup also refreshed existing rules; Codex rule changes
load on restart. No new permission grant was added by this slice. Development
activation is `none` on the next helper invocation. No product integration or
saved-data migration changed.

## Remaining boundary

Replace the explicit unfinished-controller gate only after independently
freezing/verifying source, inventory, package/assets and environment/baseline
identities, and connecting real scenario records to `EvidenceContract.validate`.
Reuse `e2e_worker.run_distribution` and the existing lease/artifact verifier;
do not repeat worker extraction or backend feasibility. Keep E2E-001 pending
until Task 19B matching is implemented. Fresh guest asset transfer, harmless
observation and authenticated secret/capture transport remain 19A acceptance
work. None of this session's dispatcher edits was exercised in a VM attempt.
