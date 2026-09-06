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

## Acceptance disposition after the evidence audit

This records evidence and gaps against the existing work/verification requirements;
it does not replace the master completion checkbox or relax acceptance.

| Boundary | Evidence or remaining work |
| --- | --- |
| Selected expected denial | `test_method_role_matrix[ListManagedUsers-child1]` passed in `/tmp/onpc-system-isjpweip/evidence`; package prerequisites also passed. |
| Selected allowed/denied pair | A selected allowed authorization case remains unproven; use an already-working case such as `test_method_role_matrix[ListManagedUsers-parent1]`, not the broken valid-password flow. |
| Original-failure preservation | `/tmp/onpc-system-sjmucss6/evidence` proves the aggregate authorization failure survives SSH, with exact scope and successful collection/cleanup. Do not repeat this qualification unchanged. |
| Deliberate harness-failure sample | Still unproven. The known product/helper authentication failure is not silently substituted for the separately required deliberate harness fault. Define its injection and expected evidence before running it. |
| Actionable diagnostic export | The latest run's private command output contains allowlisted `pam-authenticate` then `authority-response` categories. Neither appears in exported guest evidence. Fix and locally verify this boundary before another VM attempt. |
| Unselected dispatch | One current-controller run remains required. Preserve known Task 14 failures; judge F1 on dispatch, exact identities, evidence and cleanup, not authentication success. |

The next session must resolve the export gap locally first. Do not launch an
unselected run merely to rediscover the existing authentication failure. Before
any later VM qualification, state which remaining row it proves and its expected
result; reuse prior applicable evidence for the other rows. A new session does
not reset the attempt budget. Do not add retries or new acceptance requirements
because a known Task 14 case remains red.

## Continuation handoff

**Status:** selected failure classification is verified; the audit found a concrete
diagnostic-export gap. Authentication repair remains Task 14 work, not an F1 gate.

**Next-session settings:** `gpt-5.6-sol` / `medium`; model: keep; effort: raise.
**Reason:** preserve allowlisted diagnostics across the private-output/export
boundary with redaction and failure-path regressions; VM repetition cannot resolve
the demonstrated collection gap.
Confirm both in the new session. Scope remains this development/host machine and
the existing guarded `ubuntu26.04` VM.

**Proven/reuse:** exact selection/prerequisite reconciliation, selected-input
provenance, stage timing, and split outcomes are implemented. The selected success
sample remains `/tmp/onpc-system-isjpweip/evidence` (five executions). The original
failure remains `/tmp/onpc-system-206cfc36/evidence`; its aggregate SSH category was
incorrect. `record_caught_failure` now preserves the first classified failure.

The prior missing-executable diagnosis was unsupported: all six preparation tools
exist in the privileged host context, and failed directories contained no staged
inputs. A missing supplied artifact path is plausible but not proven; do not
repeat speculative tool installation. No `setup.sh` change was needed.
`artifact_source` now distinguishes missing/inaccessible/unavailable inputs before
run storage or VM access. Tool preflight also checks `dpkg-deb` and `dpkg-query`.

**Verification/evidence (2026-09-05 local):** 94 focused tests passed; isolated
cleanup safety passed 49 tests plus 3 subtests. `make check` passed 891 unit/contract
and 17 component tests plus static/traceability checks; `git diff --check` passed.
One fresh build at `/tmp/onpc-f1-20260906-preparation` records source
`89e06f07a73ba6c8ac184694db5ef5ba5ba4dcce006881c050b4213b170f7b8d`, package
`b01d31f750ab1db26bc57ff1a0dad5c23bbc3dd0f3244708e3755c0a5f8819f9`.
One guarded attempt used `AREA=authorization`
`TEST=test_real_selected_parent_authentication[child1]`;
`/tmp/onpc-system-sjmucss6/evidence/result.json` records exactly five executions,
partial scope, aggregate `pytest:failed:authorization`, and passed infrastructure,
collection, and cleanup. JUnit retains `agent:unexpected-denied`; selected-input
digest is `4bbe26089ba3bd177eaae7fe5791cc2c59111a244d2777e32571e4840910a0f1`.
Stage seconds: preparation 2.41, bootstrap 45.14, install 50.19, reboot 20.68,
tests 37.51, collection 1.63, cleanup 100.80. The runner completed cleanup and
`virsh domstate` confirmed shut off; no operation is owned. All new runner edits
were exercised; later handoff edits are documentation only.

**Next slice:** export the allowlisted authentication-helper categories currently
retained only in host-private pytest output. The latest run contains
`pam-authenticate` for the deliberate wrong password, then `authority-response`
for the expected-success attempt; exported JUnit lacks both. Use a safe fixture
to verify category retention, attempt association, and secret exclusion locally
before any VM run. Never export raw authentication terminal data. Stop at that
tested boundary and save the concrete qualification selector/fault for the next
slice. The table above owns the evidence disposition; do not restart solved
selection or aggregate-failure investigations. Task 14's handoff now records that
its diagnostic code has run and that authority response is the next boundary.
