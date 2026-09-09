# Task 20 customer reboot wiring and refused live preflight

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
Existing observation edits and concurrent unrelated work were preserved.

## Changed boundary

The [customer reboot contract](../../../tests/e2e/README.md#customer-reboot-observation-boundary)
now wires `Smoke` and `onpc_serial::run_install` through durable `reboot-ready`
and `reboot-observed` acknowledgements. Installed digest/identity, reboot marker,
unchanged boot and authenticated local serial session precede authorization.
The fixed customer command uses ordinary guest logind/Polkit policy with
`--no-ask-password`; no force, sudo-cache assumption, extra password, host reboot
or in-journey restore is added. Serial input drains before the existing changed-boot
wait. New serial login-prompt and GDM matches follow its acknowledgement; final
greeter corroboration requires the same new boot. Capture remains sealed.

Controller exceptions now latch failure, including failed checkpoints. Refusal
and ordinary smoke keep their logout flow. The installation worker budget is
960 seconds, adding 360 seconds to the ordinary 600-second budget for the
330-second reboot observation and return allowance. No lease, stream or display
replacement/reattachment behavior changed. Development activation is `none`
on invocation; no setup, product or saved-data migration changed.

## Verification and inputs

| Selection | Result |
| --- | --- |
| `tools/run-unit-tests tests/unit/test_graphical_smoke.py tests/unit/test_e2e_serial_helper.py tests/unit/test_e2e_worker_cleanup_safety.py tests/unit/test_e2e_gdm_helper.py -q --tb=short` | 132 passed, 0.91s; handle 64357, exit 0 |
| `tools/run-unit-tests tests/unit/test_e2e_install_helper.py tests/unit/test_e2e_observation_transport.py tests/unit/test_vm_transport.py tests/unit/test_e2e_matched_screens.py -q --tb=short` | 1545 passed, 22.23s; handle 68174, exit 0 |
| Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q --tb=short` | 546 passed, 3 subtests, 4.90s; handle 12714, exit 0 |
| `make check` | 5241 unit/contracts passed, 97.01s; 17 private-D-Bus components passed, 0.38s; syntax/source guards passed; handle 77215, exit 0 |
| `tools/run-tests artifacts build` | Verified; handle 63948, exit 0 |
| Dispatcher safety closure | 546 passed, 3 subtests, 5.10s |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-3vm6b092` | Failed before installation; 713.905s; handle 96301, exit 1 |

An initial affected-test selection included nonexistent
`tests/unit/test_graphical_serial.py` and was rejected before execution (exit 2).
The corrected selection passed; the actual serial transport regressions are in
`test_graphical_serial_cleanup_safety.py`, included in isolated safety.
No test assertion failed locally. Changed-document links and scoped whitespace
checks passed. Results describe captured inputs, not later unrelated edits.

Manifest: `/tmp/onpc-test-artifacts-3vm6b092/artifact-manifest.json`.
Revision: `944da18980cab1181c287ba9d59e88276cbea654`.
Source SHA256: `56c992b6ad04cbacbaf178df284c27c96b573ee255e3265067af2e318fe488a1`.
Package SHA256: `558a2f9de25349df0128826c36381947e9985902af8116b62e09fbb99378465c`.
This worker made no checkout edits during build/live execution through cleanup.
Subsequent evidence/handoff edits and concurrent source changes require new artifacts.

## Live refusal and discriminating evidence

Attempt sixteen overall: three prior qualifications passed; thirteen failed
attempts remain failed. This first attempt with reboot wiring passed source
preflight, baseline/asset verification (92 entries), GDM interactions and real
serial authentication. At `install-ready`, `VerifiedInputs.recheck()` reported
`e2e:provenance-rejected`; the installation boundary refused before its reply.
No installer command, installer password or customer reboot was issued.
Wiring is **locally tested, live unqualified**. E2E-002 and independent startup
failures remain pending. The intermittent recipient defect was not reached.

Working-tree status newly showed changes to `tools/codex_slices.py`,
`docs/TestAutomation/Unattended-Prompt.md`,
`docs/TestAutomation/Unattended-Sessions.md` and `tests/unit/test_codex_slices.py`.
Their contents and supervisor history were not read or changed. File metadata
places the first three modifications at epoch second 1788972037, between the
manifest (1788971408) and `install-ready.request.json` (1788972090623131034 ns);
the test file changed at 1788972116. These are concrete concurrent checkout
changes affecting the required source-preservation boundary.

The retained failure does not name a changed file or retain the original
snapshot comparison. The installation wrapper collapses the original provenance
code; final source preservation is false after the latch. Concurrent changes
are evidenced, but reports cannot establish the exact first mismatching file or
exclude another simultaneous provenance failure. Do not weaken metadata checks,
ignore paths or restore bytes to clear refusal. The
[owning provenance contract](../../../tests/e2e/README.md#controller-owned-provenance)
records this diagnostic limit. No second live attempt was made.

| Evidence | Location |
| --- | --- |
| Terminal outcomes, inputs, preservation and lease completion | `/tmp/onpc-graphical-smoke-zt9pfe97/result.json` |
| Unacknowledged installation preflight | Same run, `install-ready.request.json`; no reply in directory inventory |
| Durable qualification checkpoints | `/tmp/onpc-e2e-evidence-dxo6va0x` |
| Worker closure and failure | `/tmp/onpc-e2e-evidence-amduyb8p/worker-result.json` |

Infrastructure failed (`e2e:worker-execution-failed`, then final provenance
rejection); product and collection aggregates are `not-run`. Reports were retained,
but collection is not an accepted pass. An ordinary worker-report read was
permission denied and an ordinary directory glob matched nothing; approved
privileged artifact reads succeeded. No execution-policy, approval-review or
Polkit denial occurred. Raw authentication output and screenshots were not read.

## Cleanup and next action

Worker `worker-38ec611739fa46a79be057f016f7395c` has `worker_stopped=true` and
`callback_closed=true`; display closure is recorded. `shutdown_verified=false`
and no backend exit status remain failure evidence: normal worker completion
did not occur. Outer guarded restoration and baseline verification completed,
lease phase is `complete`, cleanup passed and host preservation is true.
Fresh guarded VM status is `state=5`, `id=-1`. All session commands exited;
no screenshot export, worker, lease or recovery remains.
Preparation/test/cleanup: 540.504/98.206/75.170s. The extended slice finished its
single live attempt and cleanup beyond the initial time review.

Task selection rechecked: Task 20 remains earliest ready; preserve Task 15A.
Build fresh source-bound artifacts, run isolated safety prerequisites, and make
one guarded installation/reboot attempt with no checkout edits through terminal
collection. This refusal does not restore the historical VM/writer hold or
require coordination confirmation. Diagnose any fresh refusal from current
evidence without changing provenance/ownership guards.

Next settings: `gpt-6-astra` / `high`, model keep, effort keep, Standard. Ordered
input is locally proven; live boot/serial/display continuity still needs its first
proof because this attempt stopped at a prerequisite. Task 20 estimates:
**Unknown sessions / Unknown minutes**. This failed prerequisite cost 11.9 minutes;
successful reboot, readiness/layout and independent faults remain unmeasured.
