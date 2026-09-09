# Task 20 reboot command outcome diagnosis

Task 20 remains the earliest ready unchecked entry; no bypass. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists.
This slice reused the [customer reboot contract](../../../tests/e2e/README.md#customer-reboot-observation-boundary)
and existing serial, SSH and durable-checkpoint helpers. Other edits were preserved.

## Discriminating result

Attempt eighteen overall passed provenance, all 92 asset entries, GDM, serial
authentication, sudo recipient/echo proof, installation, installed digest/identity,
reboot marker and unchanged boot/session checks. After `reboot-ready`, the real
guest command returned **nonzero**. The split shell-result marker matched; its
fixed diagnostic is `returned-nonzero`. The helper failed without retrying the
command, changing policy, sending another password or entering the boot wait.

This proves execution and failure of the customer reboot command in this
attempt. Incomplete serial delivery and a subsequent SSH boot-wait failure do
not explain this attempt. It does **not** establish the command's rejection
reason, a Polkit denial, or the cause of the preceding 330-second timeout.
No boot change, serial return, GDM return or readiness acceptance was reached.
Three historical qualifications remain passed; fifteen failed attempts remain
failed. No second live attempt was made. E2E-002 and the assigned E2E-028 faults
remain pending; visible notice rendering and readiness/layout are unaccepted.

## Implementation and corrected shared finding

Inspection found that `Smoke._step` already defers while `pending_in` is nonempty.
The previous handoff overlooked that gate. `SerialConsole.step` preserves partial
sends/backpressure, with existing behavioral regressions. No replacement drain
loop or serial transport was added. The new `reboot-input-drained` checkpoint
records the existing gate without claiming guest execution.

`onpc_serial.pm` appends a split `printf` exit-status marker to the one fixed
reboot command. Private `wait_serial` records only zero/nonzero/unobserved;
command echo cannot contain the complete marker. Nonzero fails immediately;
absent output stays unknown and still needs changed-boot evidence.
`Transport.wait_boot_change` now emits old-boot/SSH-255/changed-boot counts and
an allowlisted terminal category, retaining unknown errors and interruption.
`ReadOnlyObservations` forwards the report while preserving its failure latch.
`Qualification.progress` validates and durably checkpoints diagnostics without
completing a stage. No raw guest output, exception text, identity or secret is
included. Test-tool activation is `none`; no product/data/setup change.

The command-result refusal path is now live-qualified. The new drain checkpoint
and probe report were not reached live and remain locally tested only. A zero
command result or missing marker still requires live qualification of complete
cross-boot serial/display continuity. Missing-marker prompt retention is also
unqualified; do not assume a timed serial read leaves later prompt matching intact.

## Verification and evidence

| Selection | Result |
| --- | --- |
| Focused transport, observer, Perl serial and smoke controller modules | 1392 passed, 1.88s; handle 95356, exit 0 |
| Isolated cleanup safety plus graphical lease | 546 passed, 3 subtests, 5.05s; handle 11940, exit 0 |
| `make check` | 5253 unit/contracts and 17 private-D-Bus components passed; traceability/syntax checks passed; handle 81995, exit 0 |
| `tools/run-tests artifacts build` | Build/verification passed; handle 14170, exit 0 |
| Dispatcher's isolated safety closure | 546 passed, 3 subtests, 5.01s |
| `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-8k15gw2b` | Failed after reboot command returned nonzero; 1277.958s; handle 95625, exit 1 |

The first focused run (handle 86861) had four failures, all in updated stubs:
the missing-return-prompt mode incorrectly rejected the initial prompt, and the
reboot-order stub lacked the new drain-diagnostic branch (three variants).
Corrected stubs passed on the next run and in `make check`. A source search
named nonexistent `test_graphical_serial.py`; the actual owner is
`test_graphical_serial_cleanup_safety.py`. No approval-review, execution-policy
or Polkit denial occurred. Private artifact reads used the approved helper.
The terminal console summary truncated hashes; complete fixed result fields
were collected from retained JSON. Raw authentication/terminal logs and private
failure text were not inspected or exported.

Manifest: `/tmp/onpc-test-artifacts-8k15gw2b/artifact-manifest.json`.
Revision: `944da18980cab1181c287ba9d59e88276cbea654`.
Source SHA256: `268924c7d8044a036e07cdb7b26d3c707ae285ee6d6b76c3214d99d01144b053`.
Package SHA256: `558a2f9de25349df0128826c36381947e9985902af8116b62e09fbb99378465c`.
No checkout edits occurred during build, execution, collection or cleanup.
Subsequent documentation edits require fresh artifacts for another attempt.

| Evidence | Location |
| --- | --- |
| Terminal result, preservation, input identities and lease completion | `/tmp/onpc-graphical-smoke-qokxwd71/result.json` |
| Failed module's fixed reboot diagnostic reference | Same run, `testresults/result-smoke.json`, title `reboot-command-result` |
| Fixed command outcome | Same run, `testresults/smoke-20.txt`: `returned-nonzero` |
| Durable checkpoints | `/tmp/onpc-e2e-evidence-b2qe2c30` |
| Worker result and cleanup | `/tmp/onpc-e2e-evidence-yt1w5shs/worker-result.json` |

Infrastructure failed (`worker-execution-failed`); product/collection aggregates
are `not-run`. Backend exit status is zero but its failure artifact is present;
the runner correctly refused it and retains `shutdown_verified=false`.
Worker `worker-9e566236c70d4b7bb89f7554c13fb62e` stopped, callback closed, and
display closure was recorded. Outer baseline restoration/verification passed;
lease phase is `complete`, cleanup passed, and host/source preservation are true.
Fresh guarded VM status is `state=5`, `id=-1`. All commands exited and results
were collected; no screenshot exports, live resources or recovery remain.
Preparation/test/cleanup were 512.664/549.309/72.212 seconds. The review window
was exceeded to finish the single live attempt and its final preservation checks.

## Next bounded result

Determine the supported authenticated customer reboot path and the nonzero
command's reason. Reuse the existing secret-safe authentication and fixed
observation helpers; inspect the relevant guest logind/Polkit/systemctl contract
and add only a fixed safe rejection category if retained evidence cannot settle
it. Do not infer authorization from serial-session activity, inspect/export raw
authentication data, remove policy guards, retry the same unchanged command or
substitute a host reboot. Validate the chosen path and its refusal locally before
one fresh guarded qualification. This is ready diagnosis within Task 20, not an
outside-input blocker. Preserve Task 15A's later work and all-task VM clearance.

Next settings: `gpt-6-astra` / `high`, Standard; keep model and effort because
command execution is now proven but guest authorization and the supported
customer authentication path remain unresolved. Shared qualification claims and
links were updated; final changed-document links and scoped whitespace passed.
