# Task F1 — Focused installed diagnosis

This brings the diagnostic selection and minimum evidence work forward from
Tasks 28A/27. Extend the existing runner; do not build another VM framework or
wait for the complete CI/evidence platform. All interfaces below are **planned**
until this task's implementation and verification pass.

- Depends on: the implemented [installed runner](../../tests/integration/README.md).
- Complexity: high; selection must preserve prerequisite, ownership and result
  boundaries. Package acceptance and customer coverage are unchanged.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Objective: diagnose one installed case without rerunning unrelated test
  matrices or losing the original failure evidence.

## Work

1. Add `AREA`, optional `TEST`, and `LIST=1` to `make check-system` and the
   controller. Start with `package` and `authorization`. Use registered case
   IDs and explicit prerequisite closure; forward selections through the
   guarded guest launcher. `LIST=1` is host-safe and needs no root/VM access.
   Reject unknown, empty, incompatible or unavailable selections before VM
   mutation. Do not execute guest fixtures while listing/collecting on the host.
2. Keep the unselected command's complete implemented scope. Selected runs
   label scope and partial coverage, record expected and executed case IDs,
   and cannot satisfy full-suite acceptance. Replace hard-coded aggregate
   pass counts as the selection contract. Preserve required installation,
   activation/reboot, readiness and cleanup dependencies for every selected
   case; omit a phase only when its prerequisite contract permits it.
3. Select a success/denial pair from currently passing installed cases and
   run it independently, with isolated fixture state and real cooldown
   semantics. F1 does not require fixing Task 14's valid-password failure.
   A failure in shared setup stops dependent
   cases with an explicit incomplete outcome, preserving their pending scope.
   Never turn the remaining unexecuted inventory into passes or hide skips.
4. Add monotonic preparation/bootstrap/install/reboot/test/collection/cleanup
   durations and separate product, infrastructure, collection and cleanup
   outcomes to the existing result. Preserve original pytest failure when SSH
   transports its exit status. Validate diagnostic commands and export their
   safe failure categories; missing collection must be visible alongside the
   original failure. Reuse existing redaction and owned-process controllers.
5. Freeze selected test/helper inputs and record their digest separately from
   the verified package/fixture manifest; retain complete run provenance.
   Reuse the present builder/verification interface. Changing a selector or
   reading a handoff is not a reason to rebuild an already-verified applicable
   package. Do not claim cached package applicability without verifying its
   real build inputs, including packaging/assets/toolchain and local changes.
   Where that cannot yet be established, build fresh and record the time.
   General build caching and final combined source capture remain Task 28A.
6. Document actual focused commands and register the interface once for later
   areas and the Task 28 aliases. Keep this task bounded to selection and
   actionable diagnostics. Measure baseline/bootstrap overhead; retain the
   accepted baseline. Do not recreate it, weaken checks, or install new host
   tooling as an incidental optimization.

Proposed interface, not executable instructions until implemented:

```sh
make check-system LIST=1 AREA=authorization
make check-system ARTIFACT_DIR=<verified-directory> AREA=authorization TEST='<case-id>'
make check-system ARTIFACT_DIR=<verified-directory> AREA=authorization
```

## Verification and completion

- Host-safe tests cover selector/prerequisite resolution, expected/executed
  reconciliation, omitted cases, incorrect identities, failure categories and
  missing/unsafe evidence. Test `LIST=1` without privileged tools or VM mutation.
- Run cleanup-safety prerequisites in isolation, then one guarded selected
  known-working case and one deliberately failing harness sample. The latter
  must retain its failure, safe diagnostics, exact scope and complete cleanup.
  These can share one explicitly defined harness qualification attempt with
  isolated samples; they are not a successful product acceptance run.
- Run the unselected current suite once to verify dispatch and cleanup. Known
  Task 14 authentication failures remain product/helper work for Task 14, with
  their original nonpassing result preserved; they must not block acceptance
  of correctly functioning selection by being disguised as a runner defect.
- Run `make check` and `git diff --check`, and publish measured stage times and
  exact selectors. Acceptance requires the selector/guard/evidence assertions
  to pass, not a false claim that Task 14 or full system coverage has passed.

The next work is the early backend feasibility check, then Task 14's smallest
unresolved authentication case under the [implementation workflow](Implementation-Workflow.md).

## Continuation handoff

**Status:** ready, implementation not started.

**Next-session settings:** `gpt-5.6-sol` / `high`; model: keep; effort: keep.
**Reason:** selector and prerequisite design remains unimplemented and must
preserve VM safety boundaries. Confirm both in the new session.
This is the development/host machine; retain
the existing guarded `ubuntu26.04` VM and its established ownership contract.

**Next slice:** implement and verify host-safe case registration, selector and
prerequisite resolution, and `LIST=1` for the current installed package and
authorization areas. Plan 15–30 minutes; if the boundary is larger, checkpoint
with the exact unfinished part. Stop after this local boundary and hand off
before guarded VM qualification. Unknown/empty/incompatible selections must
fail before any VM mutation; listing must not execute guest fixtures.

**Reuse/read:** inspect the current `check-system` Make target, the existing
controller and its host-safe regressions, guided by the
[installed runner contracts](../../tests/integration/README.md#reusable-implementation-contracts).
Read only the registration/dispatch paths needed for this slice. Use the existing
interface as the starting point; selectors documented above are still planned.

**Verification:** focused host-safe tests for the new resolution/listing
behavior, existing affected guards, and `git diff --check`. Record the exact
commands, inputs and outcomes. Do not run the full installed suite merely to
start this task. Full F1 acceptance, including `make check`, remains pending.

**State/remaining:** this documentation session started no implementation or
owned operation. Preserve concurrent edits, including Task 14's unqualified
diagnostic changes. Guest selection forwarding, expected/executed reconciliation,
diagnostic stage times, input provenance and guarded qualification remain in
the task scope; retain them in the next handoff. Update
[Continuation.md](Continuation.md) to resume F1 until its full acceptance passes.
Reassess both settings for the next unfinished slice at each handoff; this
initial design recommendation does not automatically apply to later routine work.
