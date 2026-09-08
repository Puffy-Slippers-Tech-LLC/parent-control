# Task 15A catalog command lookup — 2026-09-08

Host filesystem-backed evidence only; Task 15A remains unchecked. Settings:
`gpt-6-astra` / `high`, pinned by the slice launcher. The existing
[writer-coordination blocker](../Task-19.md#task-19b-continuation--2026-09-08)
remains; no build, installed test, or VM operation was started.

## Result and limits

Sixteen new cases in `tests/unit/test_catalog_scope.py` exercise real catalog
discovery with temporary account directories, native files, symlinks and desktop
entries. Account lookup and fixed system roots are redirected into the fixture;
PATH and working-directory changes are restored by pytest. No app is launched.

The original lookup used `shutil.which` with the broker's inherited PATH. Six
initial failures established administrator substitution at each of three system
fallback positions, discovery of an administrator-only command, discovery from
the broker's current directory, and failure to canonicalize a system symlink.
The initial run had the new system-directory constant but unchanged lookup.

The fix preserves selected-child `.local/bin` and `bin` precedence, then searches
only `/usr/local/bin`, `/usr/bin`, and `/bin` for bare command names. Relative
paths containing directory components cannot enter the system fallback, because
`which` would otherwise use the broker's working directory. System native targets
are canonicalized before generic-launcher exclusion. Rejection logging uses a
fixed reason without account data, commands, paths or environment contents.

Passing cases cover child switching, both child binary directories, all three
system directories and precedence, administrator/empty/relative/unset inherited
PATH, bare and dot-relative unavailable commands, a native symlink target with
spaces, and rejection of a symlink alias for a generic wrapper. The
[application design](../../SystemDesign/Applications.md#application-policy-and-enforcement)
documents the fixed lookup policy. It does not evaluate shell profiles or
arbitrary session PATH changes. Desktop `Path` and child-candidate executable
permission semantics were not expanded in this slice.

Relevant requirement: ONPC-CORE-APPS-001. These checks do not establish installed
discovery, launcher-route agreement, kernel enforcement or task acceptance; no
requirement mapping or checklist entry was promoted.

## Verification

| Experiment | Result and timing | Preparation / cleanup |
| --- | --- | --- |
| Initial catalog/scope selection | 6 failed, 25 passed, 0.12 s; exited 1 | Temporary files only; original failures retained below |
| Final catalog and consumer selection | 173 passed plus 30 subtests, 0.36 s; exited 0 | Temporary fixtures; environment and current directory restored |
| Final `make check`, handle 10923 | 2,811 unit/contracts passed, 64.98 s; 17 components passed, 0.51 s; exited 0 | Syntax and stage traceability passed; result collected |

Initial failing test identities:

- `test_relative_exec_system_fallback_ignores_admin_path[0]`, `[1]`, `[2]`:
  selected the administrator fixture instead of the expected system binary.
- `test_relative_exec_never_uses_admin_or_working_directory_fallback[admin]`
  and `[relative]`: returned a launcher where the expected catalog was empty.
- `test_relative_exec_system_symlink_uses_canonical_native_target`: returned the
  symlink pathname rather than its native target.

Initial command:
`tools/run-unit-tests tests/unit/test_catalog_scope.py tests/unit/test_catalog.py -q`.
Final focused command:
`tools/run-unit-tests tests/unit/test_catalog_scope.py tests/unit/test_catalog.py tests/unit/test_core.py tests/unit/test_app_termination.py tests/unit/test_parent_main.py -q`.

All commands exited and results were collected. No owned process, lease,
screenshot or recovery remains; no VM state was inspected or inferred. No
approval or Polkit denial occurred. Preparation and cleanup timings were not
measured separately; no live fixture cleanup was needed. Existing unrelated
edits were preserved. Scoped whitespace and local Markdown link checks passed.

## Next boundary

With an explicit writer pause through collection, run isolated cleanup guards,
build fresh artifacts and qualify `test_native_command_policy_is_uid_scoped`
through the registered system enforcement area and its four prerequisites.
Without coordination, independent local work can extend the installed catalog
fixture/assertions for child-only, system and administrator launcher precedence,
with host regressions before any VM use. Read `system_enforcement.py:provision_native`,
`tests/system/test_enforcement.py`, `tests/unit/test_system_enforcement.py`, and
the [native registration evidence](15A-Native-Registration-20260908.md).

No expensive 15A attempt has been spent. Native routes/patterns/screen-time,
Snap/Flatpak runtime and full-area acceptance remain pending. Remaining 15A
sessions and minutes are Unknown: no live matrix timing or Snap/Flatpak helper
qualification is available. The focused host check and full host check above
provide timing for this completed local boundary only.

## Verified source identities

SHA-256 after the final code change. Subsequent documentation/handoff edits
invalidate artifact provenance and require fresh inputs for installed execution.

| Source | SHA-256 |
| --- | --- |
| `broker/oh_no_parent_control/catalog.py` | `bb2610094be4e0e5cdbf6739fea3e5fd0f8314f498dd3cccfa50ad4ccd00f35f` |
| `tests/unit/test_catalog_scope.py` | `95522b70f5e0c744626bae23fc8c0e7c6602c355029e85ebdd505dba1fbb3436` |
| `tests/unit/test_catalog.py` | `955c617142c3b562752371c3c0b6674f16f8a8bd8d67af921c060d02d3e59d57` |
| `tests/unit/test_core.py` | `38052d0834fc820e98679ad94a4556edc3b62f1adc5e337d7cc930dbc336f404` |
| `tests/unit/test_app_termination.py` | `6f02a716b5f7be4d1aa8bab3024214ac2116fe149e9dfc006c6601ad63b3e074` |
| `tests/unit/test_parent_main.py` | `09ea035a0bd44649031807ae58b1704c8794daf65101e2a9b55d2a26bbfc9359` |
