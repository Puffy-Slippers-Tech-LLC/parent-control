# Task 15A child-relative installed catalog fixtures

Date: 2026-09-08. Settings: `gpt-6-astra` / `high`, pinned by the slice launcher.
Development-host work only; the existing guarded VM authorization remains.

The registered `test_native_catalog_is_selected_child_scoped` now includes a
system launcher with a relative command. It must resolve to the selected
child's `.local/bin`, the other child's `bin`, then the first child's target
again. A lower-priority child `bin` copy and administrator `.local/bin` copies
are present. A second system launcher whose command exists only for the
administrator must stay absent from both child catalogs.

Provisioning preflights every launcher, executable and directory before writes.
New executables use exclusive creation, verified content, explicit executable
modes and account ownership. Existing account directories and unrelated files
remain untouched. The outer guest baseline owns installed fixture cleanup.
No product code, setup integration, migration or requirement mapping changed.

Host checks use actual filesystem discovery with the inherited PATH pointing at
the administrator fixture; D-Bus, account lookup and chown are substituted.
They do not establish installed broker or kernel enforcement acceptance.
Fault injections prove rejection of administrator substitution, lower-priority
selection, missing relative targets, stale child targets and administrator-only
visibility. New safety cases cover existing/dangling binary collisions and
symlink/non-directory binary ancestors before any mutation.

| Experiment | Result and measured test time | Cleanup |
| --- | --- | --- |
| `tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q` | 14 passed, 0.08 s | Exited 0; temporary filesystem fixtures only |
| `tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q` | 156 passed, 0.80 s; handle 3148 | Exited 0; results collected |
| `make check` | 2,841 unit/contracts passed in 62.94 s; 17 private-D-Bus components in 0.37 s; syntax and stage traceability passed; handle 79805 | Exited 0; private-bus fixtures completed |
| Scoped `git diff --check` and `tools/read-only links` | Passed for changed source, handoff and evidence documents | Exited 0; read-only |

Preparation and cleanup were part of the host test invocations; separate timing
was not exposed. No build or VM attempt ran, and no expensive 15A attempt was
spent. No test failed or action was denied. No owned process, VM lease,
screenshot export or recovery remains. No VM state is inferred from old evidence.

## Verified source identities

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `8b7f2d43f0a61a330415c87598b95d35445ca9630ab5bef895382fe944ece558` |
| `tests/unit/test_system_enforcement.py` | `15a21a2dee8e8bf5d42ef9a7d10abcbe9e38750d45f18f0c4cbbf93e7a37d03c` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `cad9275d8e48e93f55a8151743a218d921dbe868faa0acabf41e1d8ee22df3a9` |
| `tests/unit/test_catalog_scope.py` | `95522b70f5e0c744626bae23fc8c0e7c6602c355029e85ebdd505dba1fbb3436` |
| `broker/oh_no_parent_control/catalog.py` | `bb2610094be4e0e5cdbf6739fea3e5fd0f8314f498dd3cccfa50ad4ccd00f35f` |

Subsequent handoff/evidence edits need no product rerun but invalidate package
provenance under the current whole-checkout input contract. Preserve earlier
[registration evidence](15A-Installed-Catalog-Registration-20260908.md) with its
original inputs. [Task 15A](../Task-15.md#task-15a-continuation--2026-09-08) remains
unchecked. Live qualification requires an explicit writer pause through terminal
collection; a clean-status sample does not resolve the retained 19B blocker.
