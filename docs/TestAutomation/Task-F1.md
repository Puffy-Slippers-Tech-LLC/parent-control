# Task F1 — Focused installed diagnosis

This brings the diagnostic selection and minimum evidence work forward from
Tasks 28A/27. Extend the existing runner; do not build another VM framework or
wait for the complete CI/evidence platform. **Accepted on 2026-09-06.**
The interfaces below are implemented and verified; see the
[acceptance evidence](Evidence/F1-Qualification-2026-09-06.md).

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

Implemented interface:

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

## Acceptance disposition

All F1 criteria are met. This qualifies the runner's selection and diagnostics;
the original nonpassing Task 14 product/helper result remains nonpassing.

| Boundary | Accepted evidence |
| --- | --- |
| Host-safe selection and guards | Local selector/prerequisite, identity reconciliation, provenance, refusal, collection and cleanup regressions pass. `LIST=1` resolves the complete 225 executions without root/VM use. |
| Independent selected allowed/denied pair | Parent1 `ListManagedUsers`: five exact passes in `/tmp/onpc-system-qpzqx8ve/evidence`. Retained child1 selected denial: `/tmp/onpc-system-isjpweip/evidence`; also corroborated by the final unselected run. |
| Deliberate harness-failure sample | `/tmp/onpc-system-_kufc3hb/evidence`: fixed `harness:qualification-failure`, five exact identities, failing exit status, successful collection/cleanup. |
| Actionable diagnostic export | Final installed export retains ten correctly associated authentication attempts: two `pam-authenticate` denials and eight `authority-response` denials. All XML parses; known fixture identity/credential sentinels are absent. |
| Unselected dispatch and original failure | `/tmp/onpc-system-vbx_zcy6/evidence`: exactly 225 executions, 217 passed and eight known Task 14 failures, zero errors/skips. Product outcome fails; infrastructure, collection and cleanup pass. |
| Complete preparation timing | Initial baseline proof validation is timed on success, rejection and interruption. The final VM run records 74.561 seconds preparation, including 72.259 seconds initial proof verification. |
| Local acceptance | `make check`: 923 unit/contracts and 17 components, plus syntax/source/traceability. Isolated cleanup prerequisites and `git diff --check` passed. |

[Commands, input digests, stage durations, audits and preserved first failures](Evidence/F1-Qualification-2026-09-06.md)
are retained. Every owned command completed. The runner restored the retained
baseline and prior configuration; a subsequent read-only query confirmed the VM
off. No new baseline, overlay, VM, host tooling or product behavior was introduced.

## Fixed qualification interface

Use the existing `AREA=authorization`
`TEST=test_method_role_matrix[ListManagedUsers-parent1]` selection for the
allowed sample. Its expected result is five passed executions with successful
collection and cleanup. Reuse the retained selected child denial as the denied
half of the pair.

For the deliberately failing harness sample, the implemented
`QUALIFICATION_FAILURE=1` option uses a public pytest call hook to raise the fixed
`harness:qualification-failure` only after that selected case's real assertion
succeeds. The hook is confined to this allowlisted case and opt-in qualification
mode; its bytes enter selected-input provenance, and the result is labeled
harness qualification. Scope/refusal and failure-handling regressions are part
of local verification. The expected result is a deliberate failure with five exact execution
identities, retained fixed failure category and safe diagnostics, and completed
cleanup. This does not qualify as a product acceptance pass.

Retained package candidate: `/tmp/onpc-f1-20260906-acceptance`, source
`5584f7fe5f2aa250713f8913b73e61bedad4968e501aa3b0b9c6b5d50722b412`, package
`0f7ffa0a388ef6b5ed6d40316968ff22ab64111b7f213cd7069b637087b0055d`.
Verify availability and current package-input applicability before reuse;
these recorded hashes alone do not establish it. The prior missing-tool
diagnosis was unsupported; `artifact_source` now rejects unavailable inputs
before storage/VM access. No host-tool installation was needed.

## Completion handoff

**Status (2026-09-06):** F1 accepted. No F1 implementation or qualification work
remains. Scope was this development/host machine and the existing guarded
`ubuntu26.04` VM. The user requested completion through acceptance rather than
another bounded-slice handoff; the remaining work was completed in this session.

**Proven/reuse:** the guarded runner supports full and exact partial selections,
fixed prerequisite closure, independent selected-input provenance, complete stage
timing, and separate product/infrastructure/collection/cleanup outcomes. Its
fixed qualification mode preserves real assertions, errors and skips and cannot
be a product acceptance pass. Selected allowed/denied cases, deliberate failure,
and complete unselected dispatch have applicable evidence. All ten real
authentication diagnostics now survive public XML export with their case/attempt
association and safe categories.

**Acceptance:** 923 unit/contracts and 17 components passed. The unselected run
executed exactly 225 cases: 217 passes and eight preserved Task 14 failures.
Infrastructure, collection and cleanup passed. See the
[acceptance record](Evidence/F1-Qualification-2026-09-06.md) for commands, digests,
timings, preserved initial failures and audits. No operation is pending; exec
sessions 92498 and 54414 completed. The VM was independently confirmed off after
cleanup. Task 14's authority-response root cause remains unresolved, with its
previous diagnostic retry budget unchanged.

**Next task/settings:** Task 19P; `gpt-6-astra` / `high`; model: raise; effort:
raise. **Reason:** F1's implementation and acceptance are solved; the next task
must establish a supported graphical backend API that fits existing VM ownership
and secret-input/capture boundaries. This is a new integration uncertainty,
not a continuation of F1. Confirm the settings when beginning that task in a new
session; do not repeat F1 qualification simply to resume the backlog.
