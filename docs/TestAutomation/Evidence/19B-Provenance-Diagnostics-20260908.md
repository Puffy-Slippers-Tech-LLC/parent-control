# Task 19B — preserve preparation refusal diagnostics

**Host reporting fix verified; no graphical qualification passed.** The public
attempt again encountered concurrent checkout edits. Its pre-recorder failure
exposed loss of the specific provenance refusal, which this slice corrected.
The [earlier attempts](19B-Ordered-Recorder-20260908.md) remain failed.

## Live attempt and limits

The checkout was clean at initial inspection and again after a fresh artifact
build. That was insufficient to establish an uninterrupted qualification window.
During the attempt, unrelated changes appeared in
`docs/TestAutomation/Unattended-Sessions.md`, `tests/unit/test_codex_slices.py`,
`tools/codex_slices.py`, and `tools/setup_dependencies.sh`. They were preserved;
this slice did not inspect their contents or modify them.

The runner printed `e2e:provenance-captured`, then
`e2e:provenance-rejected`, before creating the recorder or running a graphical
worker. The retained first failure is only `execution:attempt-failed`.
Concurrent source changes are observed evidence; the exact underlying
provenance code was not retained and must not be reconstructed as a proven fact.
No screen, video, or serial execution evidence exists from this attempt.

| Operation / handle | Result |
| --- | --- |
| Artifact build / 37073 | Built and verified `/tmp/onpc-test-artifacts-wqlq876c`; exit 0. |
| Public `E2E-001` / 11203 | Isolated prerequisites: 447 passed, 3 subtests passed in 5.04 s. Invocation exit 1. Preparation 242.454 s; cleanup 70.708 s; test and collection 0 s. |
| Terminal evidence | Infrastructure failed; product and collection not run; cleanup passed; lease phase `complete`. |
| Current VM inspection | After command exit, `tools/test-vm status` confirmed off (`state=5, id=-1`). |

Retained raw directory: `/tmp/onpc-e2e-attempt-eb6yvjvg`.
Case terminal record:
`/tmp/onpc-e2e-evidence-8kwwwfzd/invocation-000003.json`.
Invocation evidence: `/tmp/onpc-e2e-evidence-02cn6e2o`.
All remain failed; the reporting fix does not rewrite them.

Recorded inputs:

- Source: `386e7981fb40f56c06976f51083fd5c11cf7c5f697695b7c6804265ef4b13add`.
- Inventory: `15fd719181f41bfb6d12ac5f30f9a02fbd652626037856e02827f8361170fe39`.
- Package: `becc87f6430908a976322275bfce067dba8c77b95144d25410a8a97dc1ba980d`.
- Assets: `344f3106413ff876f039f1004e42ef7483885c93b05f5285d4e7557b9b7021ed`.
- Baseline: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.

## Corrected boundary and host verification

`tests/e2e/execution.py:attempt_failure` preserves an explicit set of reviewed
provenance codes from `EvidenceError` before a recorder exists. It covers
preflight, capture, and contract-construction rejection, with the first refusal
checkpointed before held-lease cleanup. Arbitrary exception strings, unknown
code-shaped strings, non-string arguments, and extra arguments remain excluded.
Existing interruption and generic-failure behavior remain. No provenance,
ownership, permission, VM lifecycle, product, or saved-data rule changed.
Activation is `none`: next test invocation.

- Focused execution/provenance checks / 82970: **100 passed in 2.74 s**.
- Fourteen new regressions exercise the real attempt/collector/cleanup
  composition with substituted VM operations, including later cleanup failure
  and private-text exclusion. They establish host reporting behavior only.
- `make check` / 98536: **2,686 unit/contracts in 47.79 s**, **17 components in
  0.35 s**, syntax/source guards and stage traceability passed; exit 0.
- Scoped diff check passed. Markdown links were checked after the handoff edits.
- Verified implementation digest:
  `54d74c6986d7db5b29e6474deca1b8f9eecadc5596b15dc4a370b29437589376`.
- Verified regression-file digest:
  `bc36ca185d7ff9dfcf130f859964d4141b07e6239fd79d2e973be1ad11358ed5`.

All owned command handles exited, results were collected, and no VM worker,
maintenance operation, screenshot export, or recovery is pending. No approval
or Polkit denial occurred. Later documentation edits require fresh artifacts
for another package-bearing run. The full check is host evidence for the
checkout it read, not frozen-input release acceptance amid unrelated edits.

## Next boundary

Three public invocations across the retained records now encountered concurrent
source edits. Do not repeat based on a momentarily clean `git status` or another
fresh build. An explicit request to pause other writers is pending. After that
coordination, freeze source through each terminal result and complete three
consecutive public qualifications, with actual screen/serial/secret and cleanup
review. If coordination remains unavailable, Task 15A depends only on accepted
Task 14 and has independent local implementation work ready.

Remaining Task 19B sessions/minutes: **Unknown** until writers are paused.
The current refusal spent 313.162 seconds in preparation/cleanup and never
measured the graphical callback; earlier 90–120-minute estimates assumed an
uninterrupted checkout. Settings remain **`gpt-6-astra` / `high`**, pinned by the
slice launcher, for provenance and terminal-evidence review.
