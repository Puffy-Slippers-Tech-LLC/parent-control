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

The third slice implemented and qualified the contained worker and private
TCP-to-FD bridge with non-VM fixtures. Live compatibility remains unproven.
Scope remains the development host and existing guarded `ubuntu26.04` VM.
Reuse the [worker evidence](Evidence/19P-Worker-Bridge-2026-09-06.md) for the
current interface, source identities, retained failed/passing attempts and
verification. Earlier adapter/tooling conclusions remain linked there.

**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** private namespace isolation, start gating, descriptor handling and
normal/interrupted descendant cleanup now work locally. The remaining first
live integration crosses backend callbacks, lease-owned graphics, and safe
screen/observation evidence; that unresolved boundary still merits the current
model and effort. Confirm both next session.

Reuse `graphical_worker.Worker`, `graphical_lease.CallbackServer`,
`lifecycle_variables()`, and `Lease(..., graphics_type='vnc')`. generalhw must
use `127.0.0.1:5900` inside the worker namespace. The worker requests the display
FD lazily; all lease callbacks stay in the controller thread. Close the worker
before the callback server and outer lease. No VM lifecycle operation belongs
in the worker. The [integration guide](../../tests/integration/README.md#graphical-adapter-under-development)
describes the exact internal API and capture boundary.

**Next observable result:** wire a credential-free generalhw distribution and
fixed guarded `check_*.py` smoke, then prove real libvirt graphics-FD attachment,
GDM/menu keyboard/mouse and screen changes, plus fixed read-only observation.
Use `pkexec /usr/local/libexec/onpc-test-runner integration <check_name>`; it
runs the isolated safety prerequisites automatically. No actual generalhw
launch/distribution or guest observation command exists yet. Do not boot outside
the lease or repeat completed tooling/namespace checks solely for a fresh chat.

Verification: 29 focused worker tests; final dispatcher safety selection passed
118 tests and 3 subtests. Non-VM normal exit, controller disconnect and forced
supervisor interruption all transferred 1 MiB and confirmed both recorded
fixture processes exited. Initial collector failure is retained; its corrected
multi-pidfd wait has a regression. Final `make check` passed (1,032 unit/contract,
17 components, syntax/traceability); `bash -n setup.sh` and `git diff --check`
passed. New code has not run against the VM. Live expensive attempts: **0**.
All commands finished; fresh read-only query confirmed VM off. About 30 minutes,
including roughly ten minutes of approval/interruption; no VM cleanup time.
Concurrent edits preserved. Task 14's failures remain; 19P still needs live
smoke evidence before acceptance.

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
