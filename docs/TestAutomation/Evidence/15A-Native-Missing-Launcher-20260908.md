# Task 15A missing native launcher policy retention

Date: 2026-09-08. Settings: `gpt-6-astra` / `high`, pinned by the slice launcher.
Development-host implementation; existing guarded test-VM authorization persists.

Registered `test_native_missing_launcher_retains_policy` in installed
`enforcement`, with the existing four package/reboot prerequisite executions.
Its separate fixed fixture preserves the shared command/catalog fixtures.
After capturing the initial hard policy's source and compiled rules, the case
removes the fixture launcher while leaving its executable present. Removal
requires the guest guard and the captured regular file identity, including
device/inode, ownership, mode, link count, size and modification/change times.
Access time is excluded because catalog reads may update it. Replacements,
edits, symlinks, hardlinks and unexpected directories are refused.

The public broker catalog must omit the removed launcher. Preferences must
retain the complete saved policy before and after another `SetPreferences`
call exercises catalog reconciliation. Source and compiled rules must still
deny the selected child; direct command witnesses require child denial and
other-child allowance. Shared transitions continue through hard/soft policy,
both screen-time states, clearing policies and final restoration, with the
launcher absent. Other-child preferences remain unchanged. Guest fixture files
remain for guarded outer baseline cleanup; no new process controller exists.

Host regressions use actual temporary-file provisioning, catalog parsing,
public broker preference reconciliation and product rule rendering. OS launch,
D-Bus and installed rule compilation boundaries are substituted. Fault tests
reject stale catalog entries, policy loss before/after re-save, missing source
or compiled denials, wrong launch outcomes, other-child policy changes and
removal/restoration failures. These checks establish harness behavior, not
installed kernel enforcement. Product code, permissions, setup, migration and
requirement mappings are unchanged. Task 15A remains unchecked.

| Verification | Result and measured test time |
| --- | --- |
| Initial isolated safety selection | 46 passed, 0.14 s; exited 0 |
| Final isolated safety selection | 58 passed, 0.16 s; exited 0 |
| Initial focused selection, handle 43410 | 378 passed and 16 subtests, 1.15 s; exited 0 |
| Final focused selection, handle 48148 | 379 passed and 16 subtests, 1.20 s; exited 0 |
| Host-safe installed inventory | New case plus four prerequisites; exited 0; no VM/artifact access |
| `make check`, handle 41657 | **Failed**, exit 2: 3,023 passed, one unrelated kiosk source-contract failure, 66.79 s; later component/syntax stages did not run |
| Scoped whitespace and Markdown links | Passed for slice source, guide, evidence and handoff |

Safety command:
`tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q`.
Final focused command:
`tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_execution_policy.py tests/unit/test_core.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q`.
Inventory command:
`tools/run-tests system --list --area enforcement --test test_native_missing_launcher_retains_policy`.

The broad failure is
`tests/unit/test_kiosk_rendering.py::KioskRenderingTests::test_gateway_frame_stays_fixed_with_animated_gateway_energy`.
It expects the `randint(1, 4)` ejection-count expression; concurrent edits in
`kiosk/oh_no_parent_control_kiosk/main.py` use weighted `choices` instead.
That source was absent from initial modified-file status and modified by the
time of diagnosis; this slice did not edit it or its tests. Narrow source/status
inspection established the mismatch. No unchanged rerun or unrelated fix was
attempted. Preserve this failed result; the kiosk writer must reconcile the
assertion with the intended behavior before a broad pass can be claimed.

Preparation and cleanup were included in test commands; separate durations
were not exposed. All commands exited and results were collected. No owned
process, lease, screenshot or recovery remains. No VM operation or expensive
15A attempt started; no current VM state is inferred. No approval or Polkit
denial occurred. Unrelated edits were preserved.

## Verified source identities

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `adf9d50b01b2ad4e7c2f2022bbfa38efe3136c9ab2662f489c27f125c516d123` |
| `tests/system/test_enforcement.py` | `98a35ac249c70b3ac54b0ecf23a48a1f34e440705fda7fcdccd5494135bcaad5` |
| `tests/unit/test_system_enforcement.py` | `43e7949b96054bd7b1554a9a7af81bfeb6e10c1c447f806be20f5caec2a0b062` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `6e1adb0ed6f11ba2e76bf569fa1bb0ad10df9f613c62f47ac92bdf268651d6a3` |
| `tests/unit/test_system_runner.py` | `d55930921d54493b1e3d66274a09791ebf8ab9b0fd9ddda0a4fbb13b313be97b` |
| `tests/unit/test_authentication_evidence.py` | `f23644fcc9e179094664912ae17b061329277073a740d8b7314dea5b8aa08110` |
| `broker/oh_no_parent_control/core.py` | `3719419fcf721b76dbd12c80d02d4867622e889bb1f1345c2fd429b4727dee25` |
| `broker/oh_no_parent_control/catalog.py` | `bb2610094be4e0e5cdbf6739fea3e5fd0f8314f498dd3cccfa50ad4ccd00f35f` |
| `broker/oh_no_parent_control/execution_policy.py` | `5e4c14ee67c353d53e59493fcc8e665700f8ed168cf845b75e67305839ec437e` |

[Previous future-pattern evidence](15A-Native-Future-Pattern-20260908.md)
retains its original inputs. Slice source hashes were checked again after the
broad failure and remained unchanged. Later documentation requires fresh
artifacts. Operator clearance arrived in the maintained handoff during this
slice: finish the active local result and cleanup, then prioritize guarded VM
qualification over more local expansion. The old writer-pause hold is resolved.
The next [Task 15A](../Task-15.md#task-15a-continuation--2026-09-08) slice must
finish edits before building fresh artifacts and keep inputs stable through
terminal collection and cleanup. Preserve lease/provenance checks and diagnose
any actual refusal. Remaining task sessions and minutes are Unknown: native
routes/update, live timings and Snap/Flatpak qualification remain missing.
