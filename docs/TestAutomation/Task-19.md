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

The work list defines full acceptance. Resume the [active handoff](#task-19a-continuation--2026-09-07)
for the remaining boundary; do not rebuild already implemented interfaces.

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

**Solid progress:** implemented the scenario recorder/lease bridge and
authenticated serial forwarding; 43 new host regressions pass. The
[recording evidence](Evidence/19A-Lease-Recording-20260907.md) retains changes,
test results and exact file digests. **19A is not accepted; all 156 variants
remain pending.** Development-host and the existing guarded VM scope persist.

**Proven boundary:** `LeasedScenario` records cleanup start before the real
`Lease.__exit__`, which remains the sole restoration/release owner. Its finalizer
checks the original lease/run/domain/ledger, actual off state and provenance,
then completes ordered evidence and validates private copies while held.
`result()` also refuses release failures. `ScenarioRecorder.run_worker` forwards
same-lease provisioned credentials/serial mode and refuses secrets absent from
the collector's original frozen registry. Host tests execute the real recorder,
collector, evidence gate and lease exit; VM operations are substituted. Reuse
the separately proven [live serial/shutdown path](Evidence/19A-Shutdown-20260907.md).

**Next observable result:** wire `runner.preflight/main` to guarded public
execution, preparation-failure evidence and final invocation reporting using
this bridge. Read `tests/e2e/runner.py`, `leased_recording.py:LeasedScenario`,
`check_graphical_smoke.py:Qualification/main`, and the
[recording contract](../../tests/e2e/README.md#ordered-controller-records).
Resolve exact runnable selections, execute actual scenario callbacks, retain
first failure and account for connection-close errors. First test the public
path with temporary synthetic declarations. Keep pending cases closed; do not
relabel qualification as E2E-001 acceptance. The deliberate
`e2e:execution-controller-unfinished` gate remains.

**Scope/attempts:** public wiring required resolving the synchronous recorder's
cleanup timing and secret-registry gap first; that dependency is now tested.
No live experiment was needed. Do not recreate the bridge or repeat the resolved
console/shutdown diagnosis next session. Preparation before recorder creation
and public terminal reporting remain controller work.

**Verification/state:** final four-module selection passed 104 tests; final
`make check` (42383) passed 2,453 unit/contracts, 17 components, syntax and stage
traceability. `git diff --check` passed. All handles exited; no VM operation,
setup, export or recovery was started. Read-only VM status confirmed off
(`state=5, id=-1`). Subsequent edits are documentation only; no package artifact
is nominated. The evidence records the exact reusable focused command. A new
package-bearing attempt still needs current verified source/package inputs.

**Next-session settings:** `gpt-5.6-sol` / `high`; model: keep; effort: keep.
**Reason:** recorder lifecycle and secret forwarding have host proof; public
dispatch and failure reporting still cross ownership/evidence boundaries.
**Remaining 19A estimate:** **1–2 substantial sessions / 2–3 hours**,
moderate-to-low confidence, excluding 19B/customer scenarios. The previous
forecast was optimistic about the recorder/lease integration effort.

## Task 19B

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
