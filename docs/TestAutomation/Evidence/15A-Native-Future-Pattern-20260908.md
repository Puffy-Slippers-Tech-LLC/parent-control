# Task 15A future native filename matching

Date: 2026-09-08. Settings: `gpt-6-astra` / `high`, pinned by the slice launcher.
Development-host implementation; existing guarded test-VM authorization persists.

Registered `test_native_future_pattern_is_uid_scoped` in installed `enforcement`,
with the four existing package/reboot executions as prerequisites. It reuses
hard/soft policy transitions with screen-time disabled and enabled, preference
readback, other-child isolation and policy restoration. The deterministic native
executable uses a versioned `.AppImage` filename; this is filename matching
coverage, not an AppImage mounting or graphical-launch assertion.

The fixture initially contains one matching version and an unrelated executable
in the same directory. After witnessing the first hard policy's source and
compiled rules, the scenario creates the future matching version using exclusive
creation. It requires selected-child denial and other-child allowance, then
compares the captured rule lines with the pre-creation capture. An exact denial
for the future path is rejected, so it cannot substitute for the directory
guard. Every blocked stage requires the unrelated file's exact allowance before
the directory denial in both files. Both children must launch that unrelated
file successfully. Restored stages require pattern rules absent and all existing
targets allowed. Private captures retain the extra post-creation rule observation;
public properties use fixture labels, role labels and digests.

The fixed `pattern`, `pattern-future` and `pattern-unrelated` launch variants use
the existing guest guard, credential verification and direct one-shot `execv`.
Companion launch variants cannot provision their shared directory. Future-file
creation refuses existing files, dangling symlinks, symlinked directories and
symlinked source fixtures. No process discovery or new cleanup controller was
introduced. Guest fixture files remain for the guarded outer baseline cleanup.

Host regressions exercise real temporary-file provisioning, catalog parsing,
preference validation and product rule rendering. D-Bus and launches are
substituted. Fault cases reject missing/misordered allowances, missing directory
guards, wrong UIDs, stale rules, an exact future-path denial, unexpected launch
outcomes, changed rules/preferences and creation/restoration failures. These
results qualify harness behavior only; installed kernel enforcement is pending.
No requirement mapping or checklist entry was promoted. Product, setup,
migrations and permissions are unchanged.

| Verification | Result and measured test time |
| --- | --- |
| Initial isolated cleanup-safety selection | 29 passed, 0.12 s |
| Intermediate safety/focused selections | 44 passed, 0.14 s; 280 passed, 1.04 s; focused handle 84663 exited 0 |
| Final isolated safety selection | 46 passed, 0.15 s; exited 0 |
| Final focused selection, handle 6614 | 283 passed, 1.06 s; exited 0 |
| Host-safe installed inventory | Selected case plus four package/reboot prerequisites; exited 0; no VM/artifact access |
| `make check`, handle 59525 | 2,992 unit/contracts, 68.11 s; 17 components, 0.34 s; syntax/stage traceability passed; exited 0 |
| Scoped whitespace and Markdown links | Passed for changed source, guide, evidence and handoff |

Final safety command:
`tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q`.
Final focused command:
`tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_execution_policy.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q`.
Inventory command:
`tools/run-tests system --list --area enforcement --test test_native_future_pattern_is_uid_scoped`.

No test command failed. Preparation and cleanup were included in test commands;
separate durations were not exposed. All commands exited and results were
collected. No owned process, lease, screenshot or recovery remains. No VM
operation or expensive 15A attempt started; no current VM state is inferred.
Unrelated edits were preserved. No approval or Polkit denial occurred.

## Verified source identities

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `c1d3378056088c900328820d83bee00494b3f4805412f9cb4284c7ae4c764d09` |
| `tests/system/test_enforcement.py` | `8798bd663ba6f71fea0c38aa755006af36ce0f6d4d3132db46470d3909e3e6ce` |
| `tests/unit/test_system_enforcement.py` | `e4f818d3a52e8c37b3271735ed8cb9cf840635bda29f6f890f792ad543feabb8` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `ff45c2583f1e43960af64d0077ea1839d0caeb494bf41a2b7549122e2d864965` |
| `tests/unit/test_system_runner.py` | `91a2022ac13518d33b2eb9e826c661e8c9cc8b7b8bb57103f239cac400d21b8b` |
| `tests/unit/test_authentication_evidence.py` | `43b58f1a65cd15d8be53c2367a9fd11234a17489c0c5d706d6d0cec2ead8a884` |
| `broker/oh_no_parent_control/execution_policy.py` | `5e4c14ee67c353d53e59493fcc8e665700f8ed168cf845b75e67305839ec437e` |

[Previous whitespace evidence](15A-Native-Whitespace-Policy-20260908.md) retains
its original inputs. Later documentation requires fresh artifact provenance.
[Task 15A](../Task-15.md#task-15a-continuation--2026-09-08) remains unchecked.
Next independent result: host-validate saved-rule retention when the native
launcher disappears. Installed qualification still needs explicit writer pause
through collection. Remaining task sessions/minutes are Unknown: live timings,
native update/routes and Snap/Flatpak qualification remain missing.
