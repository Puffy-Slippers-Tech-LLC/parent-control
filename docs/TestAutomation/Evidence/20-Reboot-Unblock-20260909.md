# Task 20 reboot unblock intervention

The operator requested an intervention after Sessions 42–44. Session 45 was
already running; a normal launcher stop let it finish and clean up before this
worker edited source. The launcher stopped at the safe boundary and remains
stopped. The existing VM authorization persists. Task 20 and E2E-002 remain
unaccepted. The second corrected run established actual reboot and serial return;
the remaining graphical-match correction passes against its retained image.

## Findings and corrections

The reviewed failures did not prove three guest reboot failures: Session 42
refused changed source provenance before installation, Session 43 timed out
without command-result evidence, and Session 44 proved a nonzero command result.
[Session 45](20-Reboot-Access-Diagnostic-20260909.md) observed an access-denied
token, with a classifier wording gap that prevents identifying the exact denied
method or policy. Those historical failures remain failed.

The unprivileged `systemctl --no-ask-password reboot` assumed authority not
established by serial login. The new customer path runs a fixed `sudo -k` reboot
command, requires the full audited sudo-rs prompt, then obtains a separate
`reboot-password` acknowledgement. `REBOOT_PASSWORD` reuses the existing
getty/shell/sudo lineage, exact argv, terminal, process-continuity and echo proof;
an installation proof cannot authorize reboot. One password is submitted; a
reprompt refuses without retry. Normal inhibitor policy and private capture
remain enforced. Fixed stage diagnostics distinguish later failures.

The first new live attempt passed that proof and its command returned zero.
Boot observation then failed immediately with `invalid-boot-output`, zero probe
counts, and a verified serial-input drain. This led to a reproducible defect in
`Transport._probe_ready`: the post-SSH `Lease.guard` uses the same `Commands`
instance for `Capture.revalidate`/`qemu-img`, overwriting `last_returncode`.
The observer consequently interpreted a failed SSH probe using the guard's zero
status. Four regressions reproduced this before the fix. Capturing the SSH
status before the guard fixes the defect while retaining ownership checks and
the existing 255-only transient classification. Tests also cover valid-looking
output from a failed probe. The original live SSH status was not retained, so
the first attempt's diagnostic alone does not establish its precise SSH failure.

The second run passed changed-boot observation, including eleven transient
SSH-255 probes, and matched a fresh login prompt on the held serial stream.
GDM returned on the held display, but its old account needle failed at 87%
(tinycv's unrounded local reproduction: 0.878672780999108). The fixture label's
pixels differ from the before-product greeter. A separate fixed
`onpc-gdm-parent-installed-account` needle retains only the reviewed canonical
fixture label and its 16-pixel blur border. It matches the same full retained
image at 100%, verified with installed tinycv. `return_after_reboot` uses this
readiness-only needle; existing input/password needles are unchanged. The new
variant refuses click points, arbitrary roles/surfaces and password variants.
Permanent pixel regressions also cover bounded movement, other identity,
password-screen refusal, the original mismatch and the crop's privacy boundary.
The complete live controller acknowledgement is still pending.

The [owning contract](../../../tests/e2e/README.md#customer-reboot-observation-boundary)
records these interfaces. The [workflow](../Implementation-Workflow.md#make-every-expensive-attempt-answer-a-question)
now states that narrower failure labels do not reset the repeated-attempt count;
once an actionable defect is identified, correct and qualify it.
Test-tool activation is `none`; no product policy, setup or saved-data change.

## First corrected attempt: authentication qualified, observation failed

| Evidence | Location/result |
| --- | --- |
| Reproduction | `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-h8kv6btl` |
| Artifact manifest | `/tmp/onpc-test-artifacts-h8kv6btl/artifact-manifest.json` |
| Source revision | `944da18980cab1181c287ba9d59e88276cbea654` |
| Source SHA256 | `d04f96d9692eda9ab8f25bbe68d743fdf1619a2ede95be5b9c35734d48d6d7ae` |
| Package SHA256 | `cd509bfbdfdab8801c33712b14157a09ba66b984f55eb4b07a9fe3d0623a01c9` |
| Terminal result | `/tmp/onpc-graphical-smoke-o0_favgm/result.json` |
| Exact reboot recipient and echo proof | Same run, `steps.json`, final `reboot-password` stage |
| Fixed reboot command result | Same run, `testresults/smoke-22.txt`: `returned-zero` |
| Durable diagnostics | `/tmp/onpc-e2e-evidence-tqhy4p60/event-000033.json` and `event-000035.json` |
| Worker closure | `/tmp/onpc-e2e-evidence-bm609hn1/worker-result.json` |

Attempt twenty overall: exit 1, handle 73305, 1658.605 seconds. Infrastructure
failed; product and collection aggregates are `not-run`. Authenticated install,
installed identity/digest and reboot marker passed. The command succeeded, but
changed boot and serial/GDM return were not acknowledged. Worker
`worker-2ccd459c3caf4bdbb74cf6d2cf8a5ebe` stopped and callback/display closed;
normal worker shutdown and the final module result were absent. Outer baseline
restoration/verification, source/host preservation and lease completion passed.
Fresh guarded VM status was off (`state=5`, `id=-1`). No exports or recovery
remain. All commands exited before the observer correction was applied.

## Second corrected attempt: reboot and serial return established

| Evidence | Location/result |
| --- | --- |
| Reproduction | `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-uhxxeiyc` |
| Artifact manifest | `/tmp/onpc-test-artifacts-uhxxeiyc/artifact-manifest.json` |
| Source revision | `944da18980cab1181c287ba9d59e88276cbea654` |
| Source SHA256 | `ecf2a815949fc2e5f7e5f0af52c821afe8ef433c8e2e00adbbbdbf1d34465e7f` |
| Package SHA256 | `cd509bfbdfdab8801c33712b14157a09ba66b984f55eb4b07a9fe3d0623a01c9` |
| Terminal result | `/tmp/onpc-graphical-smoke-1bvj8nsc/result.json` |
| Command result / serial return | Same run, `testresults/smoke-22.txt` / `smoke-23.txt`: zero / fresh login prompt |
| Boot and recipient acknowledgements | Same run, `steps.json` |
| Fixed failure stage | Same run, `testresults/smoke-26.txt`: `gdm-return` |
| Failed match and reviewed image | Same run, `testresults/result-smoke.json`, `smoke-25.png` |
| Durable qualification records | `/tmp/onpc-e2e-evidence-rlpn4wpr/event-000035.json` through `event-000037.json` |
| Worker closure | `/tmp/onpc-e2e-evidence-aoash4v6/worker-result.json` |

Attempt twenty-one overall: exit 1, handle 44602, 1375.180 seconds. Preparation
543.976s, test 767.686s, cleanup 63.348s. Exact reboot recipient/echo proof,
command exit zero and input drain passed. Probe counts were old boot 0,
SSH unavailable 11, changed boot 1, outcome `changed-boot`. The old digest was
`7e979c8bd7dabde35b19f5b0fe1d5a118e400c5bb496eed427b000b61a9d53a4`;
fresh confirmed boot was
`30762868970e980399bfcfc6c3ffd241e544794197da548280af1dc835733fe1`.
Serial login returned before the graphical matcher failed. The inspected image
shows the GDM account list, including the newly installed product account.
This is real reboot/serial evidence, not a passing complete qualification.

The module result is `fail`; backend exit 0 alone does not pass the worker.
Worker `worker-6b7417ddfcdd4740b7596c1e0e6f4bb4` stopped, callback/display closed,
and normal shutdown was not verified. Outer restoration/verification, lease
completion, cleanup and host preservation passed. Fresh guarded status confirms
the VM is off. Product/collection aggregates remain `not-run`.

Final provenance also refused (`preservation.source=false`). That check includes
source, staged assets and baseline; its underlying reason was not retained.
The intervention worker made no checkout edits from artifact build through
terminal cleanup, and the launcher stayed stopped. A particular source editor
or baseline cause is not established. Preserve this refusal and report its fixed
specific reason in the next necessary run; never waive the check. No host
execution-policy or Polkit denial occurred. All commands exited before the
graphical correction. Later code/documentation edits require fresh artifacts.

Only the reviewed fixture-label crop is retained in the repository. The full
temporary screenshot export is removed after inspection; the original private
artifacts and logs remain intact.

## Verification

- Initial focused authentication, serial-parser and controller checks: 2161
  passed, 27.76s, handle 16327. Prompt fragmentation and missing-result/login
  retention execute the installed serial parser and its pipe-read path.
- Initial `make check`: 5572 unit/contracts and 17 components passed, handle 4442.
- Isolated cleanup safety: 546 tests plus 3 subtests passed, handle 58682;
  the dispatcher's closure also passed before the live attempt.
- Guard-overwrites-SSH regressions: four failed before correction as expected;
  affected transport/observer/controller selection passed 1384 afterward,
  1.46s, handle 75699. Additional valid-looking-output cases are included in
  the final checks.
- Final pre-second-attempt `make check`: 5580 unit/contracts and 17 components
  passed, handle 23915. An earlier run (7005) correctly failed the real-checkout
  provenance test because this worker added the evidence document concurrently;
  the unchanged-checkout rerun passed. That local test failure is separate from
  the later live final-provenance refusal.
- Isolated safety before the second attempt: 546 plus 3 subtests passed, handle
  57569; the dispatcher repeated the same closure successfully. Fresh artifact
  build passed, handle 46773.
- The original GDM mismatch reproduced locally using the installed matcher.
  The corrected needle then matched the full retained screenshot at 100%; 138
  affected checks passed including that temporary reproduction, handle 60591.
  The final portable pixel/helper/serial/staging selection passed 144 checks,
  5.49s, handle 93244. No permanent test depends on a `/tmp` failure artifact.
- Final `make check` after all code/needle changes: 5604 unit/contracts passed
  in 108.77s and 17 components in 0.36s, handle 92864, exit 0. The checkout was
  unchanged throughout this run. Subsequent edits only record these results.
- All six edited documents passed local link checks (153 links, zero missing);
  scoped `git diff --check` passed. The full temporary screenshot export was
  removed using `tools/cleanup-screenshots`; private originals remain intact.

The next useful complete run should include the startup audit's minimum
fapolicyd/GDM and broker reconciliation/D-Bus ordering assertions, the corrected
graphical return, and explicit final-provenance diagnosis. Implement and verify
those observations locally first. Another full installation solely to extend a
reboot diagnostic label would not advance this plan. E2E-002 readiness and the
independent E2E-028 startup faults remain unfinished; the corrected matcher has
not been exercised in a subsequent live run.
