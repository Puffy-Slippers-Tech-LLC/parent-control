# 07 — Verify the complete changed-unit scope

**Recommended model: GPT-5.6 Sol. Effort: high.** Selection and execution are
settled; switch to Astra for a newly discovered ownership/security diagnosis.

**Prerequisite:** 01–06 resolved or safely contained under the
[shared contract](README.md). **Status:** Not started.
**Next:** [08](08-host-ui-verification.md).

## Freeze the selection

Inspect both staged and unstaged changes and discover new files:

```sh
git diff --name-only HEAD -- 'tests/unit'
git status --short
```

Run the union of every changed unit file, new/untracked unit files introduced by
tasks 01–06, directly affected consumer tests, and these mandatory supplements:

```sh
tools/run-unit-tests -q 'tests/unit/test_fixture_gui_adapter.py' 'tests/unit/test_parent_discovery_worker.py' 'tests/unit/test_parent_access_worker.py' 'tests/unit/test_parent_about_worker.py' 'tests/unit/test_build_test_artifacts.py' 'tests/unit/test_support.py' 'tests/unit/test_system_enforcement.py' 'tests/unit/test_test_applications.py' 'tests/unit/test_*cleanup_safety.py' 'tests/unit/test_graphical_lease.py'
```

The command above covers the supplements, **not the entire changed-file set**.
Build a literal, quoted launcher selection for the discovered union, deduplicated
as appropriate. The launcher expands the quoted cleanup pattern; no shell
expansion, inline Python, raw pytest, command substitution or arbitrary wrapper.
For deleted tests, verify where their behavioral obligations moved; do not pass
nonexistent files or silently drop their coverage.

At plan creation the changed unit set contained these 26 files under `tests/unit/`:

| Files | Files |
| --- | --- |
| `test_accessible_e2e_ui.py` | `test_automation_ids.py` |
| `test_child_preview.py` | `test_codex_test_rules.py` |
| `test_coverage_generation.py` | `test_e2e_controller_qualification_cleanup_safety.py` |
| `test_e2e_desktop_session.py` | `test_e2e_inventory.py` |
| `test_e2e_kiosk_entry.py` | `test_e2e_runner.py` |
| `test_e2e_suite_cleanup_safety.py` | `test_e2e_terminal.py` |
| `test_feedback_collection.py` | `test_fixture_cleanup_safety.py` |
| `test_fixture_gui_adapter.py` | `test_installed_journey_cleanup_safety.py` |
| `test_kiosk_rendering.py` | `test_mutter_input.py` |
| `test_parent_main.py` | `test_prepare_baseline_tool.py` |
| `test_prepare_vm_contract.py` | `test_request_selections.py` |
| `test_setup_entrypoint.py` | `test_system_enforcement.py` |
| `test_test_applications.py` | `test_ui_cleanup_safety.py` |

This baseline is an omission check, not a substitute for fresh discovery. Source
tests of setup/VM contracts remain ordinary unit work; do not execute setup/VM
operations to validate them.

## Execution and completion

Run one suite at a time; use bounded sequential batches if necessary and record
each exact selection and actual final status. All cleanup-safety and lease
regressions must pass in isolation before host UI/fixture operations. Do not use
the handoff's 1,475-pass gate as a substitute on changed code.

On failure preserve artifacts, distinguish mechanical defects from behavioral
mismatches, and follow the shared regression procedure. A fix reopens its owning
implementation task and requires affected checks again. Do not change expected
behavior to meet this gate.

Complete only when every selected file has a final passing result, there are no
unread/running suites, and the final source/test selection is recorded. Freeze
implementation and tests for tasks 08–09; any subsequent code change invalidates
affected verification and must be tracked before close-out.
