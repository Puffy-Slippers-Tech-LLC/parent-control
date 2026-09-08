# Task 15A installed catalog registration — 2026-09-08

Host implementation evidence only; Task 15A remains unchecked. The interrupted
conversation had completed only reads, with no running command or mutation to
recover. Maintained status was reconciled before implementation resumed.
The existing [writer-coordination blocker](../Task-19.md#task-19b-continuation--2026-09-08)
remains; no artifact build or VM attempt was started.

Registered `test_native_catalog_is_selected_child_scoped` in the existing
`enforcement` area. The case provisions distinct native targets for shared
system, child and administrator desktop IDs; child-only, other-child-only and
administrator-only launchers; and a hidden child override of a system launcher.
It reads the installed broker through the parent caller while selecting child,
other child, then child again. Membership, labels, exact targets, duplicate
exclusion and a system-only launcher are checked at each step. Only role-labelled
pass properties are public. No requirement mapping was promoted.

Provisioning runs behind the existing guest guard, refuses fixture collisions
and symlink/non-directory ancestors before writes, and verifies copied executable
digests. Explicit modes survive the private controller umask. Newly created user
directories/launchers receive the selected account ownership; existing directory
modes and ownership are preserved. Outer baseline cleanup owns guest fixture
files; no new process controller or cleanup signal is introduced.

Host regressions exercise these fixtures against the real filesystem-backed
catalog implementation with temporary account/system roots. D-Bus and ownership
changes are substituted, so these tests do not establish installed behavior.
Deliberate faults cover administrator leakage/substitution, a missing child
launcher, duplicate entries, wrong labels, stale child results and a missing
system launcher. Safety tests cover guard refusal, existing/dangling launchers,
symlink/file ancestors and a pre-existing target directory symlink.

| Experiment | Result and exposed timing | Cleanup |
| --- | --- | --- |
| `tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py -q` | 10 passed, 0.07 s; exit 0 | Temporary host fixtures only |
| `tools/run-unit-tests tests/unit/test_system_enforcement.py tests/unit/test_catalog_scope.py tests/unit/test_system_runner.py tests/unit/test_authentication_evidence.py -q` | 150 passed, 0.71 s; exit 0 | No installed guest execution |
| `tools/run-tests system --list --area enforcement --test test_native_catalog_is_selected_child_scoped` | Five executions: four package/reboot prerequisites plus selected case; exit 0 | No root, artifacts or VM access |
| `make check` | Handle 10462 exited 0; 2,831 unit/contracts in 63.99 s, 17 components in 0.37 s; syntax/traceability passed | All commands completed |
| Scoped whitespace and Markdown links | Passed | No cleanup needed |

No failing experiment, approval rejection or Polkit denial occurred. Preparation
time was not separately measured; no live preparation/test/cleanup time applies.
All started commands exited and their results were collected. No owned process,
lease, export or recovery remains. VM state was neither inspected nor inferred.
Unrelated edits were preserved. Settings: `gpt-6-astra` / `high`, supervisor-pinned.

## Verified source identities

SHA-256 after final code changes. Later documentation edits change artifact
provenance and require freshly verified inputs for a package-bearing VM attempt.

| Source | SHA-256 |
| --- | --- |
| `tests/integration/system_enforcement.py` | `ea763a47075df6c978fcba9f94c24523c3fb5a08d76774f3547bfcde22700611` |
| `tests/system/test_enforcement.py` | `9e2c290fff05657fbbaba891c8d0b3403dd4843d982bb7c33eb8f2be2121437b` |
| `tests/unit/test_system_enforcement.py` | `7e163e0656289c4e4146f2e1bb5c16511565497607cb35e09d22e55d84107ccd` |
| `tests/unit/test_system_enforcement_cleanup_safety.py` | `456b837536e5bcef1e210ed69f4a0341d39ad14ec612bea773b8e2975810f9a2` |
| `tests/unit/test_system_runner.py` | `d3a0a977413e6a1dfc14132aa1cc4a7797488023f13b5313c764438361b4df8b` |
| `tests/unit/test_authentication_evidence.py` | `d2de9f7d0d667e4b37ffde013200e7a4684b52a92bafdf4af7a9cd0f31bbd66b` |

Next: qualify the catalog and native command cases after writers explicitly
pause through collection. Without that coordination, independent local work
can add child-relative executable lookup fixtures/assertions to this catalog
case. Native route/pattern/screen-time and Snap/Flatpak runtime coverage remains
pending. Remaining Task 15A sessions and minutes are **Unknown**: host timings
do not measure live matrix duration or platform-helper qualification.
