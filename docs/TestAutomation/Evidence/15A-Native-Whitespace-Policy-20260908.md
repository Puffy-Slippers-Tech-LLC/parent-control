# Task 15A native whitespace-path policy

Date: 2026-09-08. Settings: `gpt-6-astra` / `high`, pinned by the slice launcher.
Development-host implementation; existing guarded test-VM authorization persists.

`test_native_whitespace_policy_is_uid_scoped` is registered in installed
`enforcement`, with the four existing package/reboot executions as prerequisites.
It provisions the same deterministic one-shot executable under a fixed filename
containing a space, with a quoted desktop `Exec`. It reuses the native hard/soft
policy transitions with screen-time disabled and enabled, verifying preference
readback, selected-child allow/deny launches, other-child allowed launches and
unchanged other-child preferences. Policy restoration retains the existing
first-failure handling and enablement recovery.

Launch requests select only `command` or `whitespace`; they cannot supply an
executable path. Guest and credential checks precede direct `execv` of the
one-shot target, preserving the command runner's existing process ownership.
Whitespace denials require the current executable SHA-256 and selected UID in
both source and compiled rules. Intervening allowed stages reject stale matching
denials. Private rule filenames and public property names include the variant,
so a combined run retains both cases' evidence.

Host checks use real temporary-file provisioning, catalog parsing and product
rule rendering. They reject wrong hashes, wrong UIDs, path-clause substitutions,
missing/stale denials, unexpected launches, changed other-child preferences and
restoration failures. D-Bus and launch substitutions establish scenario behavior
only; no broker or kernel enforcement was exercised. No requirement mapping was
promoted. Product, setup, migrations and permissions are unchanged.

| Verification | Result and measured test time |
| --- | --- |
| Initial isolated safety selection | 19 passed, 0.11 s |
| Final `tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q` | 29 passed, 0.12 s; exited 0 |
| First focused run, handle 20547 | 2 failed, 234 passed, 1.00 s; new catalog test exhausted its account-lookup double |
| Second focused run, handle 60050 | 2 failed, 228 passed, 1.00 s; replacement account double lacked UID; redundant allow-rule variants had also been removed |
| Corrected focused run, handle 50947 | 230 passed, 0.95 s |
| Final focused run, handle 34691 | 240 passed, 0.96 s; includes whitespace other-user fault variants and distinct evidence names; exited 0 |
| Host-safe installed inventory | New whitespace case plus four package/reboot prerequisites; exited 0; no VM/artifact access |
| `make check`, handle 91411 | 2,932 unit/contracts, 64.98 s; 17 components, 0.40 s; syntax/stage traceability passed; exited 0 |
| Scoped whitespace and Markdown links | Passed for this slice's source, guide, evidence and handoff |

The final focused command was
`tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_execution_policy.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q`.
The inventory command was
`tools/run-tests system --list --area enforcement --test test_native_whitespace_policy_is_uid_scoped`.
Intermediate failures were test-double defects, not installed product results.
Preparation and cleanup were included in test commands; separate durations were
not exposed. All commands exited and results were collected. No owned process,
lease, screenshot or recovery remains; no VM operation or expensive 15A attempt
started. No current VM state is inferred from earlier evidence. Unrelated edits
were preserved. No approval or Polkit denial occurred.

## Verified source identities

| File | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `eff6b0d0094fba11fb131ae367e39ddfcf9047c9f08bfcd5643de8efa173c7a6` |
| `tests/system/test_enforcement.py` | `a2e3eae4229ef8b7a69a133711d784d317044d1cfdb2972a539ec844fb85db43` |
| `tests/unit/test_system_enforcement.py` | `c15ccf78d04aa92fe37ee6ff00bd91d4bf7c9972f5f1f960d9d8494061b13a74` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `cc288814834f995c69ac54b2483d641d9e24a895591582680a9bc379ead70126` |
| `tests/unit/test_system_runner.py` | `a58b9331778fcd68b8e5b9489d75b17c239b75064f9f878a4f805a3a05520a26` |
| `tests/unit/test_authentication_evidence.py` | `449af37630028e381cb216191f54778ae801691df3dcd42b83be56cfab114226` |
| `broker/oh_no_parent_control/execution_policy.py` | `5e4c14ee67c353d53e59493fcc8e665700f8ed168cf845b75e67305839ec437e` |

[Previous enabled-policy evidence](15A-Native-Enabled-Policy-20260908.md) retains
its original inputs. Later documentation requires fresh artifact provenance.
[Task 15A](../Task-15.md#task-15a-continuation--2026-09-08) remains unchecked.
Installed qualification needs explicit writer coordination through collection.
The next independent boundary is a native versioned-filename pattern scenario
with a future matching file and an existing unrelated same-directory executable.
Remaining task sessions/minutes are Unknown: live timings, route/pattern cases
and Snap/Flatpak helpers remain unqualified.
