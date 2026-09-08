# Task 15A native soft-policy scenario

Date: 2026-09-08. Settings: `gpt-6-astra` / `high`, pinned by the slice launcher.
Development-host implementation only; existing guarded test-VM scope persists.

`test_native_command_policy_is_uid_scoped` now exercises allow, hard denial,
restored allow, soft denial, and restored allow again with screen-time control
disabled. The intermediate source/compiled rule check and successful launch
exclude stale hard denial as the soft-policy witness. Every save reads back the
selected app state and disabled screen-time preference before checking rules
and launches. Each stage retains the unrelated child's successful launch and
unchanged preferences. Existing final restoration preserves the original failure
even when restoration also fails. Public evidence uses fixed stages and roles;
actual rules remain in existing private diagnostics.

The host rig substitutes D-Bus, launch execution and rule observations. Seven
added fault variants cover soft launch failure with successful/failed restoration,
screen-time unexpectedly enabled, hard-policy substitution, missing rules,
unrelated-child launch denial, and unrelated-child preference changes. They
stop expansion and retain failure/restoration evidence. These checks establish
scenario behavior, not installed broker or kernel acceptance. No product code,
setup integration, migration, permission or requirement mapping changed.

| Experiment | Result and measured test time | Cleanup |
| --- | --- | --- |
| `tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q` | 19 passed, 0.10 s | Exited 0; temporary filesystem fixtures only |
| `tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q` | 171 passed, 0.80 s; handle 13826 | Exited 0; results collected |
| `tools/run-tests system --list --area enforcement --test test_native_command_policy_is_uid_scoped` | Selected case plus four package/reboot prerequisite executions | Exited 0; list-only, no VM/artifact access |
| `make check` | 2,861 unit/contracts passed, 63.12 s; 17 components passed, 0.36 s; syntax/stage traceability passed; handle 18187 | Exited 0; private-bus fixtures completed |
| Scoped whitespace and Markdown link checks | Passed for changed files and handoff | Exited 0; read-only |

Preparation/cleanup were included in test invocations; separate timing was not
exposed. No failed test or approval/Polkit denial occurred. No build or VM attempt
was started; no expensive 15A attempt was spent. All commands exited and results
were collected; no owned process, lease, screenshot or recovery remains. No
current VM state is inferred from prior evidence.

## Verified source identities

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `d9fea258b1f5f24149e283892a2d9396118d047178f7541131a718de6dc91d40` |
| `tests/unit/test_system_enforcement.py` | `913b05504eee00d3186c5bb314cd0af18c1f61646506915ff05e5169d1e583e5` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `356cec20b40766ab94aec666aa27eea8437bb4e7b46319245be667fa31978a03` |
| `tests/system/test_enforcement.py` | `9e2c290fff05657fbbaba891c8d0b3403dd4843d982bb7c33eb8f2be2121437b` |

Earlier [catalog evidence](15A-Catalog-Path-Fallback-20260908.md) retains its
original input identities. Later documentation changes require fresh package
provenance. [Task 15A](../Task-15.md#task-15a-continuation--2026-09-08) stays
unchecked; live qualification requires explicit writer coordination through
collection. Remaining task estimates are Unknown: screen-time-enabled cases,
native route/pattern coverage, Snap/Flatpak helpers and live durations remain
unqualified.
