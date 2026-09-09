# Task 20 recipient diagnostics and final notice qualification

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
Existing final-notice implementation and unrelated work were preserved.

## Changed boundary

`installation_observations.py:login_identity` retains its original strict
executable resolution and every password gate. After failure, fixed diagnostics
classify the original errno, proc executable-link reread, fixed login target
resolution, selected process start-time/ancestry continuity, systemd leader
continuity, effective-root status and effective `CAP_SYS_PTRACE` bit.
Missing/replaced/zombie processes and permission/loop/not-directory/unknown errors
stay distinguishable. Only the selected process, fixed login target, own status
and fixed getty service are read; no process scan or arbitrary link target.

These sequential observations after failure are not atomic proof of its cause.
A successful reread cannot clear refusal. The observer accepts only the exact
fixed-field grammar, checkpoints before refusing, and latches failure against
later success. No raw paths, identities, exception text or authentication output
are exported. Tests cover all three identity phases, error/continuity/context
categories, private canaries, malformed output and refusal after recovery.
Development activation is `none` on invocation; no setup, product or data change.

## Verification and inputs

| Selection | Result |
| --- | --- |
| Initial three-module focused run | 1741 passed, 2 failed, 23.18s; handle 28123, exit 1 |
| `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_install_helper.py tests/unit/test_graphical_smoke.py -q --tb=short` | 1784 passed, 23.44s; handle 80495, exit 0 |
| Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q --tb=short` | 546 passed, 3 subtests, 5.20s; handle 71228, exit 0 |
| Dispatcher safety closure | 546 passed, 3 subtests, 5.32s |
| `tools/run-tests artifacts build` | Verified; handle 97108, exit 0 |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-yjxaavwa` | Passed, 1282.288s; handle 14679, exit 0 |

The two initial failures were an incorrect new test assertion: final continuity
legitimately has a read-only terminal handle open. The no-open assertion now
applies to earlier phases; all failures still require exact refusal output and
the final phase confirms handle closure. No production gate was weakened.

Manifest: `/tmp/onpc-test-artifacts-yjxaavwa/artifact-manifest.json`.
Revision: `48a6bcf01dbc9e4ef392e15f71d9a2bb3c50be6b`.
Source SHA256: `cf1aed461db2202dfbdf9253feccd78d5dd177ba3cc9f0a40352ab04373d3f21`.
Package SHA256: `d339d1839a3fabcee53d0ca099a745ceace52c580906f69e494a261fd33eec4f`.
No checkout edits occurred during build/live execution through final cleanup.
This handoff invalidates artifact reuse. Full task acceptance suites were not
run for this partial qualification.

## Live result and evidence

Attempt fifteen overall: three qualifications passed; twelve historical failures
remain failed. All 92 asset entries matched. GDM interaction, real serial login,
product absence, audited sudo-rs identity, exact prompt, recipient/echo proof,
single password submission, installed package identity, reboot marker, logout
and GDM return passed. `smoke-17.txt` records
`exact-text=1 bold-red=1 final-output=1`: the first live qualification of this
final notice assertion. It proves emitted serial bytes, not graphical terminal
rendering or reboot.

The intermittent executable refusal did **not** reproduce; its cause remains
unresolved. New diagnostics passed locally but were not triggered in the guest.
Do not claim a fix or repeat installation solely to seek this refusal.

| Evidence | Location |
| --- | --- |
| Outcomes, provenance, preservation and lease completion | `/tmp/onpc-graphical-smoke-lk1twn00/result.json` |
| Module assertions and fixed prompt/submission/notice records | Same run, `testresults/result-smoke.json`, `smoke-15.txt` through `smoke-18.txt` |
| GDM return, directly reviewed | Same run, `testresults/smoke-20.png` |
| Ordered qualification evidence | `/tmp/onpc-e2e-evidence-71524tfp` |
| Worker closure | `/tmp/onpc-e2e-evidence-gcr7ksyc/worker-result.json` |

Infrastructure, collection and cleanup passed; product aggregate is `not-run`:
helper qualification is not E2E-002 acceptance. An ordinary module-result read
was permission denied; the approved privileged reader succeeded. No approval-review,
execution-policy or Polkit denial occurred. Raw authentication capture was not read.

## Cleanup and next boundary

Worker `worker-9b055e630c334be1acae27c915ae44f9` stopped with backend exit 0,
callback/display closed and `shutdown_verified=true`. Outer baseline restoration
and verification, host/source preservation, lease completion/release passed.
Fresh guarded VM status reported `state=5`, `id=-1`. The approved screenshot
export was reviewed and removed with `tools/cleanup-screenshots`. All commands
exited; no operation, export or recovery remains. Preparation/test/cleanup:
518.529/555.039/65.996s; total includes final validation. No second live attempt.

Next extend the qualified installation with real customer reboot, changed boot
identity and reconnection, then readiness/layout and the two independent faults
from the [startup audit](20-Startup-Audit-20260908.md). Preserve ordinary smoke's
unchanged-boot contract; keep E2E-002 pending. Use the new diagnostics if recipient
refusal recurs in required work.

Next settings: `gpt-6-astra` / `high`, model keep, effort keep, Standard:
authentication/notice success is qualified, but ownership and observation
continuity across a real reboot need design and first proof.
Task 20 estimates: **Unknown sessions / Unknown minutes**. The live attempt cost
21.4 minutes; cross-boot/readiness/fault work has no measured completion bound,
and intermittent prerequisite failure remains possible.
