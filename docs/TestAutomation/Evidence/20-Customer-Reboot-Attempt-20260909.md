# Task 20 first live customer reboot observation

Task 20 remains earliest ready and unaccepted; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
This slice reused the wired [customer reboot boundary](../../../tests/e2e/README.md#customer-reboot-observation-boundary)
without changing runtime code. Existing staged and unrelated edits were preserved.

## Result and qualification limit

Attempt seventeen overall reached authenticated installation and `reboot-ready`.
Source preflight, installation provenance checks, all 92 asset entries, GDM,
serial authentication, sudo recipient/echo proof, installed package digest and
identity, reboot marker and unchanged boot all passed their checkpoints.
The prior provenance refusal did not recur: final source preservation is true.
The intermittent recipient defect did not recur either; its cause remains open.

The worker submitted the fixed customer command and published
`reboot-observed.request.json` with a null screenshot. No observation reply
exists. Checkpoint 28 started `reboot-observed` at 1025.731479 seconds;
checkpoint 29 recorded worker failure at 1355.816066 seconds: 330.085 seconds
later, consistent with the configured boot-wait deadline. Console diagnostics
reported `waiting-for-boot-change`, then `boot-change-rejected`, without a
changed-boot acknowledgement. Fresh serial prompt and GDM return were not reached.

This establishes a **failed live reboot observation**, not a proved guest reboot
failure or a timeout cause. `ReadOnlyObservations.wait_boot_change` collapses
transport errors, and the worker further records only `worker-execution-failed`.
There is no retained fixed probe history distinguishing old-boot SSH responses
from SSH status 255, nor a fixed reboot-command exit/policy result. The current
serial stage calls `SerialConsole.step()` once before the blocking observer;
that API can leave pending bytes after backpressure or a partial send. There
is no retained pending-input/drain proof for this attempt. These are evidence
gaps and candidate boundaries, not established causes. Do not infer permission
denial, stream loss, or successful command execution from command submission.

Three historical qualifications remain passed; fourteen failed attempts remain
failed. This is the first attempt to reach the wired reboot input; the previous
wired attempt stopped at provenance. E2E-002 stays pending; readiness/layout,
visible notice rendering and independent E2E-028 faults remain unaccepted.
No second live attempt was made.

## Verification and retained inputs

| Selection | Result |
| --- | --- |
| `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q --tb=short` | 546 passed, 3 subtests, 5.11s; handle 43949, exit 0 |
| `tools/run-tests artifacts build` | Build and verification passed; handle 10956, exit 0 |
| Dispatcher isolated safety closure | 546 passed, 3 subtests, 5.06s |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-fxua2u99` | Failed at reboot observation; 1559.565s; handle 39182, exit 1 |

Manifest: `/tmp/onpc-test-artifacts-fxua2u99/artifact-manifest.json`.
Revision: `944da18980cab1181c287ba9d59e88276cbea654`.
Source SHA256: `7e74cdeb6d320de14935278858f83555110e0dbac26e1bfc6e4d574a8e87fe40`.
Package SHA256: `558a2f9de25349df0128826c36381947e9985902af8116b62e09fbb99378465c`.
No checkout edits occurred during build, execution, collection or cleanup.
These subsequent documentation edits require fresh artifacts for another run.
No runtime changes invalidated the preceding focused checks or `make check`;
this slice adds live evidence, not task acceptance. Changed-document links and
scoped whitespace checks passed.

| Evidence | Location |
| --- | --- |
| Terminal result, input identities, preservation and lease completion | `/tmp/onpc-graphical-smoke-or7xi80t/result.json` |
| Installation and reboot authorization; unacknowledged request | Same run, `steps.json`, `reboot-ready.reply.json`, `reboot-observed.request.json` |
| Durable stage and cleanup checkpoints | `/tmp/onpc-e2e-evidence-y8ghjvvo/event-000027.json` through `event-000031.json` |
| Worker closure and failure | `/tmp/onpc-e2e-evidence-anqre0nv/worker-result.json` |

Infrastructure failed; product and collection aggregates are `not-run`, not
passes. An ordinary worker-report read was permission denied; the approved
privileged artifact reader succeeded. Its default 8000-byte checkpoint read
truncated JSON; explicit `--bytes 64000` enabled complete parsing and fixed-field
extraction. A private directory listing was too large and was not repeated;
raw command/authentication contents were not read. A source search named one
nonexistent helper file; the documented artifact-reader options resolved the
read without that file. No execution-policy, approval-review or Polkit denial.

## Cleanup and next bounded result

Worker `worker-7bc151095005421f8e200fb7b5efb3d7` has `worker_stopped=true` and
`callback_closed=true`; display closure is recorded. `shutdown_verified=false`
and null backend exit status retain the abnormal worker termination. Outer
baseline restoration/verification passed, lease phase is `complete`, cleanup
passed, and host/source preservation are true. Fresh guarded status is
`state=5`, `id=-1`. All commands exited and results were collected; no screenshot
export, live lease, worker or recovery remains. Preparation/test/cleanup were
490.281/866.860/70.096 seconds. The slice exceeded its initial review window to
finish the one attempt, final provenance, evidence inspection and cleanup.

Next, add narrowly scoped, privacy-safe reboot diagnostics to the existing
helpers before another live run: prove submitted serial bytes actually drain,
retain fixed command outcome categories where observable, and distinguish
old-boot, SSH-unavailable and terminal guard/probe failures while preserving
the original refusal. Validate partial-send/backpressure, command failure,
old-boot/255 and unknown-error behavior locally. Do not add a controller, retry
the command, weaken guest policy/ownership, or assume a cause. One improved
guarded attempt may then discriminate the unresolved boundary with fresh inputs
and isolated safety. Publish the result in the owning contract and reuse map.

Task selection remains Task 20; Task 15A stays preserved. VM clearance persists
without another coordination request. Next settings: `gpt-6-astra` / `high`,
model keep, effort keep, Standard: the live failure crosses customer input,
guest authorization and transport, and its cause is not yet distinguished.
