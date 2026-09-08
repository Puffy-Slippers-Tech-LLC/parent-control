# 15A first native runtime qualification — 2026-09-08

Scope: development host builds and host safety tests; installation and launch
probes only in the existing guarded VM. Settings: `gpt-6-astra` / `high`, pinned
by the slice launcher. This is failed partial qualification, not 15A acceptance.

## Verified correction and execution

The first `tools/run-tests system --artifacts
/tmp/onpc-test-artifacts-wtp8px6y --area enforcement` invocation exited 1 before
VM access: its unprivileged safety phase passed 505 tests but raised 14 setup
errors in `test_catalog_collision_preserves_existing_files`. The shared
`installed_catalog_tree` fixture imported the broker catalog through ambient
`PYTHONPATH`; the privileged dispatcher intentionally supplies a clean environment.
The standalone launcher had passed 519 tests plus three subtests in 5.92 seconds,
so that result alone did not establish dispatcher compatibility.

The fixture in `tests/unit/test_system_enforcement.py` now uses pytest's
`monkeypatch.syspath_prepend` to resolve its checkout broker dependency for the
fixture lifetime. No dispatcher environment or permission was widened.
`tools/run-unit-tests tests/unit/test_system_enforcement_cleanup_safety.py
tests/unit/test_system_enforcement.py -q` passed 220 tests in 0.47 seconds.

Fresh `tools/run-tests artifacts build` output:
`/tmp/onpc-test-artifacts-ctwjiujg`. The corrected invocation was
`tools/run-tests system --artifacts /tmp/onpc-test-artifacts-ctwjiujg --area enforcement`.
Its clean-environment safety phase passed 519 tests plus three subtests in
5.73 seconds. The run acquired the lease, validated inputs, installed, rebooted,
executed all nine declared cases, collected evidence and completed cleanup.
Handle 41060 exited 1. No checkout edit was made by this slice during the run.

## Result and discriminating evidence

Retained public evidence root: `/tmp/onpc-system-kdn0c1bg/evidence`.
Read it through the documented `onpc-test-artifacts` helper. `result.json`
reports product failed (`pytest:failed:enforcement`), infrastructure passed,
collection passed and cleanup passed, with `cleanup_phase=complete`.
`guest/installed.xml` and `guest/rebooted.xml` each report two passed prerequisites.
`guest/enforcement.xml` reports five tests, four failures, no errors or skips:

| Case | Observed boundary |
| --- | --- |
| `test_native_command_policy_is_uid_scoped` | Initial allow for both children and hard denial/other-child allow passed. Restored source/compiled rules matched allowance, but the selected-child launch failed `enforcement:expected-allow`. |
| `test_native_whitespace_policy_is_uid_scoped` | Initial allow passed for both children; hard source/compiled hash rules were present; selected-child launch failed `enforcement:expected-denial`. |
| `test_native_future_pattern_is_uid_scoped` | Initial target/unrelated allowance passed; hard rule witnesses and future fixture creation passed; original target launch failed `enforcement:expected-denial`. Future denial/unchanged-rule assertions were not reached. |
| `test_native_missing_launcher_retains_policy` | Initial allowance passed; missing catalog entry, saved-policy retention through re-save and hard rule witnesses passed; selected-child launch failed `enforcement:expected-denial`. |
| `test_native_catalog_is_selected_child_scoped` | Passed selected-child, other-child and selected-child-again catalog assertions. |

All four policy cases recorded preference restoration; that property does not
prove restored live kernel enforcement. Later soft/enabled transitions did not
run. No requirement mapping or checklist completion was promoted.

`guest/service-journal.txt` records the first hard command ruleset identity,
followed immediately by a debdb trust-database refresh. Two command-target
denials follow, including the restoration-time denial; no later ruleset identity
appears in the collected journal. The broker log records later reconcile/save
acceptance. `FapolicydPolicy._reload` currently checks only the exit
status of `fagenrules --load`; it does not witness the daemon's active ruleset.
**Hypothesis, not yet proven:** accepted saves can precede live ruleset activation
while the daemon refreshes trust data. File readback is insufficient to establish
the live boundary. Do not repair this by retrying failed launch assertions or
adding arbitrary sleeps. Verify the supported reload/activation contract first.

## Provenance, cost and next experiment

| Identity | SHA-256 / revision |
| --- | --- |
| Build source revision | `b93cf2225b72d91db38a9b633dda03ffd2180217` |
| Build source content | `84551cf324441fd58d017d8e25918118e4f2968cb284e52dc18e0f11e215cbc5` |
| Package | `1f240892f2710514ae0ff16599c9b5c3ea85773e2de128af89d4a1d24c22f389` |
| Fixture | `1b2aee47186c5057c581a6777c64f1ed7b40e960f47cc4e676e5628753074365` |
| Selected inputs | `de197bbb6c82d4c307a62a9499c1ae676f3a885784e89687e084d55ecfab35d8` |
| Baseline provenance | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |

| Experiment | Preparation / execution / cleanup cost | Outcome |
| --- | --- | --- |
| First dispatcher preflight | Safety 5.90 seconds; no VM operation | 14 fixture import errors; retained failure, corrected locally. |
| Corrected full registered native area | Preparation 69.374; bootstrap 46.256; install 49.604; reboot 20.119; tests 46.065; collection 1.585; cleanup 92.230 seconds | Approximately 5.4 minutes in recorded controller stages; five total passes and four failures. |

Two artifact builds passed; no build-duration total was exposed. One live 15A
attempt has been spent on the activation boundary; the prior refusal never
entered the controller. No unchanged live retry occurred. After collection,
checkout HEAD was observed at `dde97bf2ee5db883bf417bd5399694e1d6a70568`;
this report retains the actual build identity rather than substituting that
revision. Handoff/document changes also require fresh artifacts next time.

Next read: `broker/oh_no_parent_control/execution_policy.py:_reload/reconcile`,
`tests/unit/test_execution_policy.py`, `tools/execution_policy_ready.py`, and
the retained service journal. Establish supported live activation semantics,
add focused behavior/failure coverage for the demonstrated cause, then rebuild
and select `test_native_command_policy_is_uid_scoped` with its prerequisites.
Use its restored-allow and subsequent soft/enabled transitions to discriminate
activation behavior before repeating the larger native area.

All session commands exited. Current `tools/test-vm status` returned state 5,
ID -1 after cleanup. The runner's baseline/host restoration checks passed;
no owned process, lease, screenshot or recovery action remains. No approval or
Polkit denial occurred. Source logs and failed artifacts were preserved.
Full 15A sessions/minutes remain **Unknown**: native activation is unresolved,
and remaining routes, update cases and Snap/Flatpak helpers are unqualified.
Handoff/evidence link checks passed (three documents, 11 links); scoped
whitespace checks passed. The active task handoff contains 368 source words.
The earlier broad-check kiosk failure remains historical evidence in the
[retention report](15A-Native-Missing-Launcher-20260908.md); no broad suite was
rerun or claimed passing in this slice.
