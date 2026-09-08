# Task 15A catalog precedence — 2026-09-08

Host filesystem-backed regression evidence only; 15A remains unchecked. The
[writer-coordination blocker](../Task-19.md#task-19b-continuation--2026-09-08)
remains in force. No artifact build, installed run, or VM operation was started.
Settings were `gpt-6-astra` / `high`, pinned by the slice launcher.

## Result and scope

Thirteen new cases in `tests/unit/test_catalog_scope.py` call the real catalog
discovery code over temporary child, other-child, administrator and system
directories. Only account lookup, system directory roots and the inherited
environment are substituted. The fixtures neither install nor launch apps.

Coverage includes child-only and system-only entries, child overrides with
spaces in their targets, child switching without catalog reuse, administrator
HOME/XDG launcher exclusion, symlinked child Flatpak exports with full refs,
system directory order, flat/nested desktop IDs, hidden/non-displayed overrides,
minimal hidden entries, missing Exec, malformed entries and unavailable/replaced
account refusal with fixed non-PII diagnostics.

The initial tests exposed four real failures: discovery skipped a child's
`Hidden` or `NoDisplay` entry, then returned a lower-priority Flatpak-exported
launcher with the same desktop ID. `list_apps` now records each encountered ID
before parsing/visibility filtering, preventing lower-priority substitution.
Unrelated visible launchers still appear. Existing count-only discovery logging
remains unchanged and no paths or account data are added to logs.

This implements the desktop-ID precedence rule in the
[Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry/latest/file-naming.html)
and honors its [visibility keys](https://specifications.freedesktop.org/desktop-entry/latest/recognized-keys.html).
The application design now describes that behavior. Relevant specification:
ONPC-CORE-APPS-001. Installed discovery, kernel enforcement, and requirement
acceptance are not established by these local tests; no mapping was promoted.

## Verification

| Experiment | Result and exposed timing | Preparation / cleanup |
| --- | --- | --- |
| Initial catalog/scope selection against unchanged catalog implementation | 4 failed, 13 passed, 0.08 s; exited 1 | All four visibility/desktop-ID variants returned the masked ID; host temporary files only |
| First fix with catalog and affected consumers | 154 passed, 30 subtests, 0.33 s; exited 0 | No installed state or process fixture |
| Final focused selection after adding minimal/invalid override cases | 157 passed, 30 subtests, 0.33 s; exited 0 | All commands completed |
| Final `make check`, handle 31801 | 2,795 unit/contracts passed, 63.48 s; 17 components passed, 0.35 s; exited 0 | Syntax and stage traceability passed; result collected |

Final focused command:
`tools/run-unit-tests tests/unit/test_catalog_scope.py tests/unit/test_catalog.py tests/unit/test_core.py tests/unit/test_app_termination.py tests/unit/test_parent_main.py -q`.
Scoped whitespace and Markdown link checks passed. Preparation and cleanup time
were not separately measured; no VM time applies. No approval or Polkit denial
occurred. All owned commands exited; no process, lease, screenshot export, or
recovery remains. Current VM state was not inspected or inferred. Existing native
registration and unrelated launcher edits were preserved. The full check is a
host result for the working tree, not package provenance or release acceptance.

## Verified source identities

SHA-256 after the final code change. Subsequent handoff edits change artifact
source provenance, so the eventual installed attempt needs fresh inputs.

| Source | SHA-256 |
| --- | --- |
| `broker/oh_no_parent_control/catalog.py` | `736f302f007a56760b5661b5aa5864d60988ec8b17f0e8320be962d8b2ae796a` |
| `tests/unit/test_catalog_scope.py` | `9aabe25ac1c67668df6e1fd3f08a0fd8321a95ee471ec32679bea85a63762e2b` |
| `tests/unit/test_catalog.py` | `955c617142c3b562752371c3c0b6674f16f8a8bd8d67af921c060d02d3e59d57` |
| `tests/unit/test_core.py` | `38052d0834fc820e98679ad94a4556edc3b62f1adc5e337d7cc930dbc336f404` |
| `tests/unit/test_app_termination.py` | `6f02a716b5f7be4d1aa8bab3024214ac2116fe149e9dfc006c6601ad63b3e074` |
| `tests/unit/test_parent_main.py` | `09ea035a0bd44649031807ae58b1704c8794daf65101e2a9b55d2a26bbfc9359` |

## Next boundary

Without writer coordination, extend these local fixtures to relative Exec
resolution: distinguish selected-child binaries, system fallback and an
inherited administrator PATH. Current tests use absolute native targets; their
administrator exclusion result does not establish command lookup isolation.
Read `catalog.py:_executable_target` and the new fixture module. With explicit
writer pause through collection, resume the registered native enforcement
qualification described in [15A's handoff](../Task-15.md#task-15a-continuation--2026-09-08).
No expensive 15A attempt has been spent. Native route/pattern/screen-time,
Snap/Flatpak runtime and full-area acceptance remain pending; total remaining
sessions/minutes are Unknown until live helper and matrix timings exist.
