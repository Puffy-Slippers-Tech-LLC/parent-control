# Task 15A native policy with screen-time enabled

Date: 2026-09-08. Settings: `gpt-6-astra` / `high`, pinned by the slice launcher.
Development-host implementation; existing guarded test-VM authorization persists.

`test_native_command_policy_is_uid_scoped` now repeats its allow, hard denial,
restored allow, soft denial and restored allow sequence with screen-time control
enabled. It enables through public `SetParentControl`, preserving the original
daily allowance, and checks enablement, allowance and unchanged app choices
before continuing. Every policy save reads back those settings and app choices;
source/compiled rules and selected/unrelated-child launches remain required at
each stage. This supports ONPC-CORE-APPS-006 scenario development, without
promoting any requirement to installed runtime coverage.

Restoration uses `SetParentControl` to disable and then restores original
preferences, attempting both even if disabling fails. Marking enablement before
its call ensures that a lost reply after a write still triggers restoration.
Final readback checks original preferences and other-child isolation. A cleanup
failure fails an otherwise successful case; an earlier scenario failure remains
the primary error. Outer guarded baseline cleanup remains authoritative.

The host rig models the broker rule that `SetPreferences` cannot change
enablement. Twenty-two added fault variants cover enabled hard/soft failures,
wrong screen-time/app/rule observations, other-user changes, rejected or lost
enable replies, enablement/allowance/app corruption, and restoration failures
with and without an original scenario error. These use substituted D-Bus,
launch and rule observations; they do not prove actual broker or kernel behavior.
Product, setup, migration, permission and requirement mappings are unchanged.

| Experiment | Result and measured test time | Cleanup |
| --- | --- | --- |
| `tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q` | 19 passed, 0.11 s | Exited 0; temporary filesystem fixtures only |
| `tools/run-unit-tests tests/unit/test_system_enforcement.py -q` | 50 passed, 0.21 s, intermediate before final fault additions | Exited 0 |
| `tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q` | 193 passed, 0.89 s; handle 27199 | Exited 0; collected |
| `tools/run-tests system --list --area enforcement --test test_native_command_policy_is_uid_scoped` | Selected case plus four package/reboot prerequisites | Exited 0; no VM/artifact access |
| `make check` | 2,883 unit/contracts, 63.65 s; 17 components, 0.42 s; syntax/stage traceability passed; handle 96416 | Exited 0; private-bus fixtures completed |
| Scoped whitespace and Markdown links | Passed for this slice's source, guide, evidence and handoff | Exited 0; read-only |

Preparation and cleanup were included in test invocations; separate durations
were not exposed. No test failure or approval/Polkit denial occurred. All
commands exited and results were collected; no owned process, lease, screenshot
or recovery remains. No VM operation or expensive 15A attempt started, and no
current VM state is inferred from earlier evidence.

## Verified source identities

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `04568cabf757ae1fc7281db5b19ea5fe0f7598b35e1f7611e9aef5671a395a44` |
| `tests/unit/test_system_enforcement.py` | `7f5f91746e27adbad420d9e33b21fc171e561a77daff7f718325678d607eadf2` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `356cec20b40766ab94aec666aa27eea8437bb4e7b46319245be667fa31978a03` |
| `tests/system/test_enforcement.py` | `9e2c290fff05657fbbaba891c8d0b3403dd4843d982bb7c33eb8f2be2121437b` |

[Previous soft-policy evidence](15A-Native-Soft-Policy-20260908.md) retains its
original inputs. Later documentation changes require fresh artifact provenance.
[Task 15A](../Task-15.md#task-15a-continuation--2026-09-08) remains unchecked.
Installed qualification needs explicit writer coordination through collection.
Independent next work is the native whitespace-path scenario and hash-rule
observations. Remaining task sessions/minutes are Unknown: live durations,
route/pattern cases and Snap/Flatpak helpers are still unqualified.
