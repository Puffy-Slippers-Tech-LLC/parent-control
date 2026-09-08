# Task 19B — first passing public runtime

**E2E-001/gdm-observation passed through terminal exit 0. Visual review is
unfinished, so this is not Task 19B acceptance.** No code changed in this slice.
The earlier provenance failures remain failed; the all-task VM clearance remains
effective and no coordination confirmation is required.

## Reproduction and evidence

Build: `tools/run-tests artifacts build`, handle 62914, exit 0, output
`/tmp/onpc-test-artifacts-gy_2nxe5`.
Public attempt: `tools/run-tests e2e --artifacts /tmp/onpc-test-artifacts-gy_2nxe5 --scenario E2E-001`,
handle 8496, exit 0. Its isolated prerequisites passed **519 tests and three
subtests in 4.97 seconds**. No checkout edits were made through finalization.
Other work was preserved; its index state changed during the run, but the
runner's source-preservation checks passed.

- Invocation evidence: `/tmp/onpc-e2e-evidence-4fuuxc8q`.
- Case terminal: `/tmp/onpc-e2e-evidence-uio_xmuv/invocation-000003.json`.
- Case run: `scenario-729aeb92bbff49adb10f41570f9230bd`.
- Raw directory: `/tmp/onpc-e2e-attempt-mi5_kzc2`.
- Worker: `/tmp/onpc-e2e-evidence-xj0ao8ld/worker-result.json`.
- Private match record: raw directory's `testresults/result-smoke.json`.

| Input | SHA-256 |
| --- | --- |
| Source | `be3ee891e984e6c26ff2e3e3ee72077e338367e9ba41362b2341cd1c982950af` |
| Inventory | `15fd719181f41bfb6d12ac5f30f9a02fbd652626037856e02827f8361170fe39` |
| Package | `0b1328cd53aecf4c24f7e0aa2ce6129467105cb7196c0032b995d9bc3592e7ac` |
| Assets | `11bfd5a9fa850e8f787632324e9ea0a4b49316e07ef0b0ba42ba908becc63a2d` |
| Baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Worker distribution | `970ba820f1a4e85ba8ea810d0e06ce11a88bcd306fe4424e15971330f06151b4` |

## Verified scope and review gap

All nine ordered observations passed with a consistent real boot identity.
The structured serial observation verifies an active local serial session and
actual command marker; logout and GDM return report no unexpected user session.
Six positive needle matches have 100% similarity. The deliberate account-list
match on the password prompt correctly returned no match (similarity zero).
Final GDM match detail 12 follows serial logout detail 11. Initial, dismissed
and returned PNG digests agree, which is allowed because serial leaves GDM
unchanged. The case's `matched-screens.evidence` retains dimensions and digests.

Collection and all terminal outcome categories passed with no first failure.
The collector verified registered-secret exclusion for retained evidence.
Raw terminal/capture data remain private and are not claimed redacted.
`NOVIDEO=1` remains the established secret-safe configuration: no video exists
or was reviewed. Raw visual inspection of `smoke-1.png`, `smoke-6.png` and
`smoke-16.png` is still required.

**Concrete review gap:** both maintained and installed
`tools/onpc-export-screenshot` accept only
`/tmp/onpc-graphical-smoke-<run>/testresults/<image>.png`.
`tests/e2e/execution.py:attempt` creates `onpc-e2e-attempt-*` instead.
No export was attempted, no approval/Polkit denial occurred, and no alternate
copy, alias or permission change was used. A tool refresh alone cannot repair
this maintained contract mismatch. Next, align future public graphical attempt
storage with the existing approved screenshot scope, with focused path/cleanup
regressions; do not broaden the export permission. Reassess qualification reuse
for that change. This run remains a runtime pass with visual acceptance pending.

## Checks, timing and cleanup

`make check`, handle 66440, exited 0: **3,057 unit/contracts in 65.11 seconds**,
**17 components in 0.29 seconds**, syntax and stage traceability passed.
Stage timings: preparation **361.591 s**, test **583.290 s**, cleanup
**68.167 s**; worker **38.328 s**. These stage totals omit substantial held-lease
finalization/provenance time and must not be treated as full invocation duration.
One attempt plus review consumed this slice; no second expensive attempt started.

All command handles exited. Worker stopped, callback closed and shutdown
verified; baseline restoration, source/host preservation and collection passed;
lease phase `complete`. Fresh `tools/test-vm status` returned off (`state=5`,
`id=-1`). No export, owned process, maintenance operation or recovery remains.
Later handoff edits require fresh build artifacts. Scoped links and whitespace
checks accompany those edits. Settings: **`gpt-6-astra` / `high`**, pinned by the
slice launcher. Remaining sessions/minutes: **Unknown** until the review path
is repaired and the applicable three-run qualification scope is established.
