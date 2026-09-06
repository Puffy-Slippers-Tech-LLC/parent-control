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

### Active handoff — 2026-09-06, 19P incomplete

The fifth slice proved automatic cleanup after graphics RPC disconnection and
fixed a confirmed outgoing AppArmor FD denial. **Live graphics still fails; no
screen/input/SSH-observation stage has completed.** Scope remains the development
host and existing guarded `ubuntu26.04` VM. Start with the
[descriptor evidence](Evidence/19P-Descriptor-Transport-2026-09-06.md), which
retains exact inputs, timings and the next discriminating experiment.

**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** lifecycle cleanup and basic FD transfer in both directions are now
proven. The live graphics RPC still fails despite those passes, requiring focused
syscall/API and security reasoning; neither a cheaper model nor lower effort is
yet warranted. Confirm both next session.

**Required next-session outcome — explicit user instruction:** solve a substantive
problem and verify the fix before handing off. The primary target is working
graphics attachment and the first real guest screen, with successful cleanup.
Instrumentation, a narrower hypothesis, or another failed attempt alone does
not satisfy this instruction; do not simply leave implementation of the fix to
yet another session. If a demonstrated external blocker prevents resolving
graphics, document its evidence and solve another ready, authorized backlog
problem instead. Time estimates are progress-review points, not sufficient
reason to defer the same unresolved problem. Preserve all safety, experiment
and cleanup constraints. The final report must identify the problem actually
solved, the change, passing verification, and precisely what remains.

**First diagnostic step, not the session deliverable:** use a small lease-owned
attachment diagnostic to distinguish failed `recvmsg` from absent/truncated
`SCM_RIGHTS`, retaining raw
syscall evidence privately. Compare the public caller-supplied and daemon-created
socket APIs under the same attempt if needed. Verify collection/failure handling
locally first; do not rerun distribution/worker qualification or launch another
full smoke just to diagnose attachment. Basic probes now pass, so no further
confinement expansion is justified by current evidence.

**Proven interfaces:** `Adapter.open_display()` isolates graphics RPCs from the
lease's lifecycle connection, verifying URI/UUID/instance/XML around attachment.
The kernel identified an outgoing `file_receive` denial with peer `snap.code.code`.
The approved, syntax-validated libvirtd anonymous-stream peer rule is installed;
`setup.sh` reproduces it without adding ptrace or QEMU permissions. The dispatcher
`integration check_graphical_transport` now proves outgoing RPC refusal and one
usable incoming FD from an owned fixture under libvirtd's enforced profile.
Both passed at `/tmp/onpc-graphics-transport-y6k4uz6a/result.json`. The final change
only adds failed-fixture summary retention; that failure branch was not live-run.

**Attempts: 4 total, 2 this slice.** Attempt 3's caller-owned API failed before
the policy fix; attempt 4's daemon-created FD still failed afterward, with no new
kernel AppArmor denial. Both original failures and empty steps are retained;
both completed ordinary cleanup and journal `complete` (348.588/373.217 s total).
No third full smoke this slice. Final `make check` passed: 1,114 unit/contracts,
17 components, syntax/traceability. Isolated safety: 148 tests and 3 subtests.
All commands finished; fresh query confirmed VM off. Approximately 40 minutes
including approval waits and cleanup overrun. Concurrent edits and Task 14's
failures remain. First screen, safe evidence and qualification remain required.

## Task 19A

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
  2. Add `tests/e2e`, its distribution/entry point, public console definitions,
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
     customer actions use the real guest UI. Separate provisioning, observation,
     and declared fault controls so a helper cannot silently set grants,
     preferences, authentication results, session state, or expiry outcomes.
  5. Pass credentials through os-autoinst secret variables and its secret-safe
     password API. Exclude them from screenshots, output, and vars artifacts.
  6. Implement bounded startup, shutdown, interruption, copied-artifact
     collection, and ownership-recorded cleanup. Add guard and cleanup-safety
     regressions, including identity replacement and rejected source disks.
  7. Prove one fresh guest boots, executes a harmless serial command, returns
     evidence, and shuts down. Document console, secret, asset, and helper
     contracts for 19B and later scenarios.
  8. Establish `tests/e2e/scenarios.json` from E2E-Coverage.md with stable scenario
     and variant IDs, category, owner, requirement links, preconditions, ordered
     steps, interventions, assertions, executable references, and expected
     evidence. Future cases remain explicitly pending. Enumerate the coverage
     dimensions before implementing them, using its bounded-matrix rules.
     Establish the minimum versioned evidence fields and safe collector now;
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
