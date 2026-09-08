# Task 19 — os-autoinst end-to-end test distribution

Execute 19P, 19A and 19B separately under the
[implementation workflow](Implementation-Workflow.md). Reuse the implemented
[baseline validation and artifact contract](../../tests/integration/README.md)
on the existing fixed VM. Read the mandatory
[real operations and scenario coverage contract](E2E-Coverage.md). No new VM, snapshot, or overlay may bypass the approved ownership workflow.

## Task 19P

- Title: Prove graphical backend compatibility before expanding coverage.
- Depends on: the implemented guarded lease; F1 is preferred for common
  diagnostic evidence but is not a graphical feasibility dependency.
- Complexity: high; a supported automation backend must fit existing ownership.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Check current primary documentation for a maintained graphical backend
     that can control the existing lease-validated VM without a second guest,
     new overlay/snapshot, private API, host-window automation, or a different
     lifecycle owner. Evaluate the proposed os-autoinst integration first.
  2. Use one bounded smoke to prove real guest keyboard/mouse, screenshot and
     supported observation transport with the existing lease and cleanup.
     Follow isolated cleanup-safety prerequisites before live controls. If
     host tools are missing, record them and update `setup.sh` as needed under
     normal authorization; do not silently recreate the baseline.
  3. Record the supported backend/version/API, smallest working invocation,
     secret-input/capture boundaries, actual timings and remaining helper gaps.
     This is feasibility evidence, not E2E acceptance or the full 19A runner.
     Also identify availability of a reproducible offline game for Task 26C
     and any required external-delivery test profile; do not download a game
     or send feedback merely to inventory prerequisites.
- Verification: source-backed compatibility and one clean guarded smoke, plus
  focused checks for any helper code and `make check`/`git diff --check` when
  code changes. Apply the two-attempt diagnostic limit. If no supported path
  is established, record the concrete blocker and stop backend development;
  independent installed-system work may proceed. Do not mark 19P complete.
- Completion criteria: a supported integration is demonstrated with retained
  evidence and safe cleanup. Carry its implementation into 19A; do not repeat
  this feasibility investigation at every graphical task.

### Completion handoff — 2026-09-06, 19P accepted

**Completed:** three corrected-input full smokes (12–14) passed on the existing
guarded `ubuntu26.04` VM. Private review confirmed the real GDM account list,
mouse-selected empty credential prompt, and Escape return in every attempt.
Infrastructure, collection, host preservation and baseline cleanup passed.
The [acceptance evidence](Evidence/19P-Screen-Input-2026-09-06.md) retains exact
inputs, screen digests, timings and original failures. This establishes backend
feasibility; it does not accept the full 19A runner or customer E2E coverage.

**Correction:** the earlier stale-controller handoff was wrong. Smoke 13 was
still running after its command session ID was discarded; its final result is
passed/complete. The redundant invocation correctly refused the busy lease.
No controller repair, recovery, lock removal or process signal was needed.
The workflow now requires retaining and polling command session metadata.

**Reuse:** `os-autoinst=5.1768577300.b85e4864-1`, public test API 48 and
`generalhw`; `Adapter.open_display()` with public `openGraphicsFD(0, 0)`;
the namespace bridge and existing lease lifecycle owner; exact QEMU AppArmor
peer rule; observer-only SSH; and `GENERAL_HW_VNC_DEPTH=32`. The bounded
ten-second render settling and large fixed-baseline tile remain feasibility
helpers. Task 19B replaces geometry/readiness with needles. Invoke the smoke
through `pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_smoke`.
The dispatcher supplies isolated safety prerequisites. Preserve private capture
handling and the [downstream prerequisite inventory](Evidence/19P-Backend-Preflight-2026-09-06.md#capture-cleanup-and-downstream-prerequisites).

**Session result:** reviewed smoke 13 (222.031 s), completed and reviewed smoke
14 (218.304 s), and passed `make check` (1,190 unit/contracts, 17 components,
syntax and traceability) plus `git diff --check`. Review exports were deleted
through the approved helper; raw evidence remains private. The final runner
exited successfully with `lease_phase=complete`; no VM operation is pending.

**Next action:** Task 14 subsequently passed final acceptance; proceed to
[Task 19A's active handoff](#task-19a-continuation--2026-09-07). The previous
Polkit investigation and 19P qualification are complete. Use the active
handoff's settings for the next slice.

## Task 19A

Accepted on 2026-09-07; the work list below defines the accepted scope.
The [completion record](#task-19a-continuation--2026-09-07) links its evidence.
Continue with [19B](#task-19b-continuation--2026-09-08).

- Title: Add the guarded os-autoinst worker and console transport.
- Depends on: Task 19P and F1; the preferred schedule follows Task 14.
- Complexity: very high. Guest ownership, storage, secrets, console transport,
  and cleanup must be correct before any graphical scenario can be trusted.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Work:
  1. Reuse 19P's demonstrated backend and F1's selection/evidence conventions.
     Revalidate the compatibility decision only if the backend, environment or
     ownership contract changed. The guarded lease remains lifecycle owner;
     no second guest, new overlays/checkpoints or private APIs are permitted.
  2. Complete the existing `tests/e2e` distribution/entry point, public console definitions,
     configuration templates, read-only guest assertion scripts, and launcher
     for the verified backend. Pin required maintained tooling through
     `setup.sh` and the test-tool list. Never use a root-password shortcut or
     attach to any VM except the lease-validated test VM.
  3. Validate the retained product-free baseline, restore it only before/after a
     complete attempt, and transfer digest-verified assets without writable
     host shares. Add `make check-e2e ARTIFACT_DIR=... SCENARIO=<id>`; refuse
     `VM_IMAGE`. No checkpoint/resume operation is available within a journey.
  4. Provide guest keyboard/mouse graphics and supported read-only observation
     transport. Keep complex assertions in versioned guest scripts/pytest;
     asserted customer actions use the real guest UI. Apply the
     [prerequisite contract](E2E-Coverage.md#prepare-prerequisites-through-supported-helpers):
     unrelated setup uses bounded supported helpers with verified real state.
     Keep provisioning, read-only observation and declared fault capabilities
     separate; record normal fixture events without disguising them as UI input
     or faults. No helper may manufacture a grant, authentication, session or
     expiry outcome that the journey claims to prove. Extend the existing
     controller only for the concrete assigned capability; no general guest
     command API or replacement orchestration framework is needed.
  5. Pass credentials through os-autoinst secret variables and its secret-safe
     password API. Exclude them from screenshots, output, and vars artifacts.
  6. Implement bounded startup, shutdown, interruption, copied-artifact
     collection, and ownership-recorded cleanup. Add guard and cleanup-safety
     regressions, including identity replacement and rejected source disks.
  7. Prove one fresh guest boots, executes a harmless serial command, returns
     evidence, and shuts down. Document console, secret, asset, and helper
     contracts for 19B and later scenarios.
  8. Reuse the established `tests/e2e/scenarios.json` and validate its stable scenario
     and variant IDs, category, owner, requirement links, preconditions, ordered
     steps, interventions, assertions, executable references, and expected
     evidence against E2E-Coverage.md. Future cases remain explicitly pending.
     Audit assigned dimensions before implementing gaps, using its bounded-matrix
     rules. Integrate the existing versioned evidence fields and safe collector;
     Task 27 extends them instead of requiring a rewrite of every scenario.
     Future pending entries do not block runner acceptance, but remain required
     for their owning tasks and the final gate.
- Verification:
  - Run cleanup-safety regressions in isolation before starting a guest.
  - Run host-safe guard/refusal tests and the fresh-guest serial smoke.
  - Check baseline/source/host preservation and secret exclusion.
  - Verify runner guards reject in-journey snapshot/checkpoint requests and
    state-writing observation helpers. Inspect the smoke's action trace and
    distinguish outer reset, real machine actions, observations, and cleanup.
  - Run `make check` and `git diff --check`.
- Completion criteria: a guarded outside-guest runner provides working graphical
  and observation transports on the approved VM, owned cleanup, redacted
  artifacts, and the enumerable scenario contract. No backend compatibility
  or customer coverage is claimed without executed evidence.

### Task 19A continuation — 2026-09-07

**19A accepted; solid progress made.** The new public
`E2E-034/serial-controller` qualification passed actual fixture provisioning,
verified asset transfer, eight serial/graphical worker stages, all scenario
assertions, secret-checked collection, baseline restoration and final invocation
exit 0. The [acceptance audit](Evidence/19A-Controller-Acceptance-20260907.md)
covers all eight deliverables and preserves exact inputs, failures and timings.

The first live attempt exposed a missing selected-input manifest in public SSH
preparation. The controller now fsyncs that input before VM acquisition and
checks the credential tool pin. A regression executes the real bootstrap
composition. The corrected attempt passed through the ordinary launcher;
no inventory override, new cleanup owner or backend change was needed.
**All original 156 cases, including E2E-001, remain pending.** The additional
qualification establishes harness behavior only.

Final `make check` (14188) passed 2,502 unit/contracts, 17 components, syntax
and stage traceability; 17 new host cases were added. Both live attempts and
all command handles exited. Handle 33292 survived a chat interruption and was
resumed without duplicate execution. Final VM status was off (`state=5, id=-1`).
No operation needs recovery. Later edits are documentation only; new
package-bearing attempts require fresh verified build inputs.

**Remaining 19A: zero sessions.** Use the [19B handoff](#task-19b-continuation--2026-09-08)
for the next implementation result and settings. Do not reopen public dispatch,
bootstrap, serial transport or controller acceptance merely because the chat is new.

## Task 19B

Accepted on 2026-09-08; the work list below defines the accepted scope.
See the [acceptance audit](Evidence/19B-Acceptance-20260908.md).

- Title: Add stable screen matching and graphical smoke.
- Depends on: Task 19A.
- Complexity: medium. This uses the established runner and console contracts.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Add reusable login/GDM, console-switching, and screenshot helpers and initial
     needles. Match small stable regions/text, use explicit click points, and
     exclude clocks and animation instead of matching entire screens.
  2. Add the smoke scenario: boot a fresh product-free guest, recognize GDM,
     switch to serial, execute a harmless command, switch back, record a
     screenshot, and shut down.
  3. Document helper usage, match deadlines, failure artifacts, and exact smoke
     invocation for later scenario tasks.
- Verification:
  - Run cleanup-safety regressions in isolation, then run the graphical smoke
    three consecutive complete qualification attempts, resetting the baseline only
    outside attempts. Mark this `runner-smoke`, not customer acceptance.
    This repetition qualifies the new harness; the ordinary suite runs the
    registered smoke once per attempt, not three times on every invocation.
  - Review screenshots, video, serial output, secret exclusion, and cleanup.
  - Run `make check` and `git diff --check`.
- Completion criteria: stable public-API graphical/serial automation is ready
  for user journeys, without host-window automation, unguarded domain access,
  or VM state shortcuts. Screen/step evidence records actual input and outcomes.

### Task 19B continuation — 2026-09-08

**19B accepted — three consecutive complete public qualifications passed.**
Qualification 3 passed E2E-001/gdm-observation, nine ordered observations,
six 100% matches, the deliberate mismatch and all terminal gates. Direct review
confirmed initial GDM, the empty focused `[Parent user]` prompt and GDM return.
The [acceptance audit](Evidence/19B-Acceptance-20260908.md) maps every deliverable
to evidence and retains exact inputs, invocation, verification and cleanup.
This is runner-smoke qualification; customer cases remain pending.

The dispatcher passed 521 isolated safety tests and three subtests. The prior
final-code `make check` remains applicable; no implementation changed here.
No test failed or action was denied. A truncated diagnostic JSON read was
recovered with the helper's bounded larger read. Original failures and the
excluded unreviewed runtime pass remain preserved in earlier evidence.

**Cleanup:** build 91346 and public run 56706 exited 0. Worker/callback shutdown,
collection, source/host preservation and baseline restoration passed; final
lease phase `complete`. Fresh VM status was off. All three private review
exports were removed through the approved helper. All commands exited; no
owned operation or recovery remains.

**Next selection:** [Task 20](Task-20.md#task-20-continuation--2026-09-08) is the
earliest ready unchecked entry, now that 19B is accepted. Audit E2E-002 and the
assigned E2E-028 variants, then implement the first bounded clean-install
journey capability. Preserve [15A's saved work](Task-15.md#task-15a-continuation--2026-09-08).
No earlier entry is bypassed. The operator's all-task VM clearance remains
effective; no renewed coordination confirmation is due. Build fresh inputs
after these documentation edits when the next live selection is ready.

**Next-session settings:** follow [Task 20's active handoff](Task-20.md#task-20-continuation--2026-09-08)
and [Continuation.md](Continuation.md). The shared model policy supersedes
the old blanket pin; the settings in previous qualifications record those runs.
**Remaining 19B:** **0 sessions / 0 minutes**; all acceptance requirements passed.

#### Previous qualification 2 handoff (superseded by acceptance above)

**Public qualification 2 of 3 passed.**
E2E-001/gdm-observation exited 0 with nine ordered observations, six 100% positive
matches, the deliberate mismatch, serial command and terminal cleanup passed.
Initial GDM, the selected `[Parent user]` empty password prompt and post-serial
GDM return were directly reviewed through the unchanged guarded exporter.
See [qualification 2 evidence](Evidence/19B-Qualification-2-20260908.md) for
exact inputs, private evidence, timings and the reusable invocation.

The dispatcher passed 521 isolated safety tests and three subtests. No code,
helper or permission changed, and no failure or denial occurred this slice.
Package, fixtures, inventory, baseline and worker distribution match
[qualification 1](Evidence/19B-Storage-Qualification-20260908.md); source/asset
identity changes reflect its documentation handoff. That evidence retains the
storage fix, corrected two-test fixture failure, 90 focused passes and applicable
`make check` (3,060 unit/contracts, 17 components, syntax/traceability).

**Next bounded result:** fresh build and public qualification 3, then the
acceptance audit. The [earlier runtime pass](Evidence/19B-Public-Runtime-20260908.md) lacks visual
review and does not count toward the required three; do not move or alias its
old captures. Preserve qualifications 1 and 2 unless relevant implementation/tool/input
changes invalidate their behavior. Raw captures remain private; video is disabled
by the established secret-safe contract and is not claimed reviewed.

**Selection and scope:** 19B remains the earliest ready unchecked task, with
19A accepted. The all-task VM clearance below remains effective. Task 20 follows
19B acceptance; preserve 15A's independent saved work. No earlier entry is bypassed.

**Current cleanup:** build 86081 and public run 79356 exited 0.
Worker/callback shutdown, baseline restoration, host/source preservation and
collection passed; lease phase `complete`. Fresh VM inspection confirmed off.
All three review exports were removed through the approved helper. No owned
operation or recovery remains. Handoff edits require fresh build artifacts,
not repetition of the retained reviewed qualifications.

**Current next-session settings:** `gpt-6-astra` / `high`; model: keep; effort:
keep, pinned by the slice launcher. **Reason:** two complete public qualifications
now pass; one repetition and acceptance remain.
**Remaining 19B:** **1–2 sessions / 30–55 minutes**, based on one further roughly
23-minute invocation plus build, review and acceptance, assuming no new failure
or relevant code change. Stage totals alone omit finalization time.

#### Previous preparation handoff (retained failure context)

**19B remains unchecked; 19A remains accepted.** The canonical ordered E2E-001
recorder and six-match reconciliation remain implemented. This slice fixed
pre-recorder provenance diagnostics: reviewed fixed refusal codes now survive
cleanup, while arbitrary exception text stays private. Fourteen new host
regressions passed. See [current evidence](Evidence/19B-Provenance-Diagnostics-20260908.md)
and the [ordered-recorder record](Evidence/19B-Ordered-Recorder-20260908.md).
Dev-host/existing guarded VM authorization persists.

**Operator clearance — 2026-09-08:** the
[all-task VM clearance](Implementation-Workflow.md#vm-availability-for-all-tasks)
resolves the pending writer-pause request and supersedes contrary scheduling
instructions in both linked evidence records. Finish any active local slice
and cleanup, then resume public E2E-001 qualification with fresh artifacts.
Carry the clearance into subsequent handoffs. The guarded runner still checks
ownership, provenance and cleanup for each attempt.

**Historical failed attempts:** a third public invocation encountered concurrent
source edits despite clean status before/after building. It rejected provenance
before graphical execution; the old handler retained only
`execution:attempt-failed`, so its exact underlying code is unproven. The
reporting gap is now locally corrected. The operator clearance above supersedes
the pending coordination request; a clean-status sample alone was not the
basis for clearing it. Preserve unrelated edits listed in the
evidence. No permissions, provenance exclusions, or manifests were changed.

**Next observable result:** with the operator hold cleared, three consecutive public
E2E-001 qualifications, with private screen/serial/secret-exclusion and terminal
cleanup review. Build fresh inputs using `tools/run-tests artifacts build`, then
`tools/run-tests e2e --artifacts <new-output> --scenario E2E-001`.
No further standalone helper diagnosis is indicated. Read
`execution.py:attempt_failure,attempt`, `controller_qualification.py:matched_screens`,
and the [public contract](../../tests/e2e/README.md#maintain-declarations).
Do not defer these runs for the resolved coordination request. At the next safe
boundary, return to 19B before more [Task 15A](Task-15.md#task-15a) work. After
19B's full acceptance, select [Task 20](Task-20.md), then resume 15A's saved
handoff. A new deferral requires current evidence and a return condition under
the [task-selection rule](Implementation-Workflow.md#start-with-one-bounded-result).

**Verification and cleanup:** focused checks 82970: 100 passed. Final
`make check` 98536: 2,686 unit/contracts, 17 components, syntax and traceability
passed. Scoped diff/link checks passed. Public handle 11203 exited 1 after
447 safety tests plus 3 subtests passed; preparation/cleanup took 313.162 s.
Case evidence is `/tmp/onpc-e2e-evidence-8kwwwfzd/invocation-000003.json`;
raw input/output is `/tmp/onpc-e2e-attempt-eb6yvjvg`. Infrastructure failed;
product/collection did not run; cleanup passed with lease phase `complete`.
All handles exited, current VM status is off, and no exports or recovery remain.
Original failed evidence is unchanged; no approval/Polkit denial occurred.
Source digests are in the evidence; reporting and later documentation changes
invalidate the live attempt's artifact inputs.

**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep,
pinned by the slice launcher. **Reason:** provenance diagnostics are host-proven;
live ordered evidence and terminal cleanup still need qualification.
**Remaining 19B:** sessions **Unknown**, minutes **Unknown** pending live results;
three complete qualifications remain, and no current public callback duration
was measured. 19A needs zero further sessions.
