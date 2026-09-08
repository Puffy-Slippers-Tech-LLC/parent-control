# Task 19B — canonical ordered public smoke

**Solid implementation progress; public qualification is not accepted.**
E2E-001 now has an executable callback with ordered GDM, serial and final
screen evidence. The public attempts were stopped by checkout changes before
graphical execution. No successful public qualification is claimed this session.
The earlier [helper qualification](19B-GDM-Matching-20260908.md) remains valid
for its recorded inputs; do not repeat its backend or needle investigation.

## Implemented boundary

- `controller_qualification.py` implements `E2E-001/gdm-observation` through
  the accepted controller, credentials, asset transfer and sole lease owner.
  Stable `step-1`/`step-2`/`step-3` IDs group the actual transport observations.
- `SERIAL_STAGES` now includes `gdm-return`: nine acknowledged observations
  independently read the same boot identity. After actual serial logout, the
  worker records that boundary, selects graphics, matches GDM and waits for
  the controller's independent session-free greeter acknowledgment.
- Every observation has a durable recorder checkpoint before its reply can
  permit the next input, including observations within a shared journey step.
- After worker shutdown, the final step reconciles the completed public module's
  six ordered needle matches. The return match must follow recorded serial
  logout. Each match requires successful areas at the existing 100% threshold
  and its private PNG. Only fixed labels, dimensions and SHA-256 enter reviewed
  evidence. Identical initial/return pixels are allowed; serial leaves GDM alone.
- The post-password explicit capture route remains sealed. No raw screenshot,
  terminal log, secret variable or arbitrary module field is exported. The
  existing authenticated worker policy retains `NOVIDEO=1`.
- E2E-001 supersedes the duplicate E2E-034/serial-controller declaration and
  retains its preparation, credential/asset, command, boot, session-isolation
  and terminal evidence guarantees. Historical E2E-034 acceptance is unchanged.
  The inventory has 33 families / 156 variants: one ready canonical runner smoke,
  155 pending customer/fault variants. Ready does not mean passed. No product
  requirement mapping, product data, setup, baseline or lifecycle owner changed.
  These test changes activate on invocation (`none`).

## Verification and attempts

| Operation / handle | Result and scope |
| --- | --- |
| Focused helper/callback/inventory/runner checks / 26253 | 221 passed in 2.11 s; initial new rejection tests had used the wrong exception class, corrected before this pass. |
| Recorder/execution/provenance regression checks / 6752 | 265 passed in 3.24 s. Synthetic fixtures now explicitly retain their 600-second/no-credentials contract instead of inheriting the live smoke's new prerequisites. |
| Final `make check` / 8195 | 2,540 unit/contracts in 42.48 s, 17 private-D-Bus components in 0.47 s, syntax/source guards and stage traceability passed. **19 additional cases** over the incoming 2,521. |
| Isolated safety selection / 34255 | 447 passed and 3 subtests in 4.73 s. Both public launchers also ran these prerequisites independently. |
| Artifact builds / 13021, 52425 | Both built and verified successfully. No product installation on the host. |
| Public invocation / 22792 | Source preflight rejected before lease acquisition; preparation 0.986 s, no worker or VM attempt. Concurrent daily-guide edits changed the package/source identity. |
| Rebuilt public invocation / 19694 | Passed preflight and preparation, then rejected `provenance:source-changed` during callback setup. New unrelated checkout files appeared while the run held its captured inputs. No graphical worker ran. Preparation 391.632 s, callback/test 281.459 s, cleanup 68.998 s. Exit 1. |

The first broad check exposed synthetic-fixture assumptions about E2E-001's
old deadline, pending status and absence of credentials. Their explicit test
contracts were corrected; no runtime guard or assertion was weakened.

The second live invocation's rejection is explicit in
`/tmp/onpc-e2e-evidence-02jt3p05/acceptance-rejected.json`:
`code=provenance:source-changed`. The first failure remains
`scenario-step-failed` in setup. Later missing-step, collection and cleanup
gate failures are preserved. Physical restoration reached lease phase
`complete`; this does not turn its failed cleanup/evidence contract green.
The original report remains intact.

Retained paths:

- First preflight refusal: raw `/tmp/onpc-e2e-attempt-ucl1rfz2`, case evidence
  `/tmp/onpc-e2e-evidence-s8ardqu6`, invocation `/tmp/onpc-e2e-evidence-03fu9_6h`.
- Held-lease refusal: raw `/tmp/onpc-e2e-attempt-zv9pnf47`, case evidence
  `/tmp/onpc-e2e-evidence-02jt3p05`, invocation
  `/tmp/onpc-e2e-evidence-dgk_agsl/invocation-terminal-candidate.json`.
- Rebuilt inputs: `/tmp/onpc-test-artifacts-avd_50cd`; source
  `df504345c919dd2cb1ba20a7876186acdcf787e59243b17537e418d28fd6a5f8`;
  inventory `15fd719181f41bfb6d12ac5f30f9a02fbd652626037856e02827f8361170fe39`;
  package `e9fbbd5f1a6445fae31ffa0aa16406f2af607a36589bb34ac09a83c6c31fcf1f`;
  baseline `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.

All command handles exited. `tools/test-vm status` confirmed
`state=5, id=-1` after restoration. No worker, VM maintenance attempt, screenshot
export or recovery is pending. No new screenshots/video exist to review from
these refused invocations. No token-usage telemetry was exposed.

## Next attempt, without another loop

Two invocations encountered changing inputs. Do not run another until other
checkout writers are paused for the complete run; this condition was requested
during the session but not confirmed before handoff. In particular,
`docs/TestAutomation/Unattended-Prompt.md` and `tools/codex_slices.py` appeared
during the second attempt and were left untouched. They are not this task's
implementation or validation. Preserve concurrent daily-guide edits as well.
The final host check predates those unrelated additions and this evidence file.

With a stable checkout, build fresh inputs using `tools/run-tests artifacts build`,
then run `tools/run-tests e2e --artifacts <new-output> --scenario E2E-001`.
Keep source files unchanged through final exit. Complete three consecutive
qualifications, inspect actual private screen/serial evidence and final gates,
then perform Task 19B acceptance checks and mark its checklist entry complete.
Do not exclude files, alter manifests, weaken provenance or repeat standalone
helper qualification to avoid the concurrent-edit refusal.

**Remaining 19B:** one substantial uninterrupted session, approximately
90–120 minutes after writers are paused; allow another correction session if
the first real callback run exposes a new defect. All three public successes
remain required. This estimate is lower than the incoming 2–3 hours because
the callback, reconciliation and host regressions are now implemented.
