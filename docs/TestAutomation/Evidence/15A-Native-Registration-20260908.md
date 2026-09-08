# Task 15A native command registration — 2026-09-08

Host implementation evidence only. Task 15A remains unchecked. The existing
[19B writer-coordination blocker](../Task-19.md#task-19b-continuation--2026-09-08)
was preserved; no VM attempt or artifact build was started.

The new `enforcement` area registers
`test_native_command_policy_is_uid_scoped`, with four package/reboot prerequisite
executions. The case calls the installed broker, verifies its catalog target,
changes the selected child's policy through allowed/hard/restored states with
screen-time control disabled, and launches as both the selected child and a
second child at every transition. It captures source/compiled rule text privately,
records digests and role-labelled witnesses, and attempts policy restoration
without replacing an original assertion failure. The existing outer VM baseline
remains the cleanup boundary for installed fixture files.

The one-shot native fixture replaces the credential-verified probe process via
`execv`, retaining the existing command controller's pidfd identity. Only
permission-denied execution errors yield a denial witness; missing files,
malformed output, missing identity confirmation, and wrong exit status fail.
Explicit directory permissions prevent the controller's private umask from
creating a misleading Unix permission denial.

No installed runtime behavior is claimed. Relevant pending specification scope
is ONPC-CORE-APPS-001/003/004/006/007/008 and ONPC-CORE-ACCOUNTS-004. Requirement
mappings and the master checklist were not promoted.

| Experiment | Result and exposed timing | Preparation / cleanup |
| --- | --- | --- |
| Isolated enforcement/caller/runner cleanup tests | 43 passed, 0.13 s | Host-only checks; exited 0 |
| Final focused enforcement/safety/runner/qualification selection | 134 passed, 2.95 s; handle 52776 exited 0 | Temporary test fixtures only; commands completed |
| Public system listing for the new case | Exactly five executions, installed/rebooted/enforcement phases; exited 0 | No privilege, artifacts, guest fixtures, or VM access |
| First `make check` | 2,764 passed, one failure, 54.14 s; handle 63652 exited 2 | Authentication-evidence synthetic registry omitted the new area; fixed its inventory, retaining original failure |
| Corrected `make check` | 2,765 unit/contracts passed, 58.11 s; 17 components passed, 0.44 s; handle 91180 exited 0 | Syntax and stage traceability passed; all command handles exited |

Added 24 host regressions across the native helper, cleanup guards, phase
selection/provenance and result reconciliation. No product code, permission
rules, host product state, accounts, or VM state changed. No approval or Polkit
denial occurred. No owned process, export, lease, or recovery remains; VM state
was not inspected or inferred from earlier evidence. Scoped diff and Markdown
link checks passed. Preparation time was not measured separately; no live VM
preparation, test, or cleanup time applies.

## Verified source identities

SHA-256 after the final code change; later handoff/documentation edits do not
change these host-code identities. They do change the current artifact source
digest, so any eventual VM run needs newly verified inputs.

| Source | SHA-256 |
| --- | --- |
| `tests/integration/system_runner.py` | `05e9ddf443dd1fbfd9a5abea69fbc42656fb8e9017ba415588cf8e7d66731d64` |
| `tests/integration/system_enforcement.py` | `3e10a3df7259be24b1420c967c8bbf3ddffdf63389acfd80e8f171c8c087a2b4` |
| `tests/system/test_enforcement.py` | `de7e0183e113115d67bfda99b68bec1cc2fcd445876c3c6a32cb2362c7e02e42` |
| `tests/unit/test_system_runner.py` | `6df25bcae2b419c4860a7609f8a5e6f4345025dc7f2ff3ed8fa105039b3109d0` |
| `tests/unit/test_system_enforcement.py` | `0ce0a841a7e78d79af04aac94ab4f631b93242f77bdb90cb28b6e018491d3c0f` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `677be61459d20ffa645996adf7780d5d5656cb0f508cec26ec524f6c3c0ff4d9` |
| `tests/unit/test_authentication_evidence.py` | `6baa85c97c7fd8bb0aa5dbc30aa41e4456a08ece0b0dc8b49f2ec7d5c20bc8f9` |

Reusable checks: `tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_system_enforcement_cleanup_safety.py tests/unit/test_system_runner.py tests/unit/test_system_qualification.py -q`;
`tools/run-tests system --list --area enforcement --test test_native_command_policy_is_uid_scoped`.
