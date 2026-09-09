# Task 20: retained sudo recipient refusal

## Result and scope

Task 20 remains earliest ready and unaccepted. Actual settings:
`gpt-6-astra` / `high`, Standard. All-task guarded VM clearance persists;
no earlier task was bypassed. Existing staged and unrelated edits were preserved.

The sudo proof returns an allowlisted first-failing condition while retaining
its identity, argv, ownership, ancestry, process-continuity and terminal checks.
Exceptions, process identifiers, command bytes and terminal data are never
serialized. The controller validates the complete response after its second
ownership check, persists a refusal checkpoint, and latches failure before any
password reply. Diagnostics cannot complete a proof step. Checkpoint failure
also prevents authentication and retry.

Changed code: `installation_observations.SUDO_PASSWORD`,
`ReadOnlyObservations.read`, and `check_graphical_smoke.Smoke` / `Qualification`.

## Verification

- `tools/run-unit-tests tests/unit/test_e2e_install_password_observation.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_installation_boundary.py tests/unit/test_e2e_install_helper.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py -q`:
  **265 passed, 1.05s**, handle **31819**, exit 0. Covers every diagnostic
  condition, private read failures, process changes, descriptor closure,
  malformed output, ownership loss, checkpoint failure and durable refusal.
  The earlier four-module check passed 194 tests before checkpoint integration.
- `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
  **526 passed, 3 subtests, 5.16s**, handle **80940**, exit 0.
- `tools/run-tests artifacts build`: handle **54007**, exit 0,
  `/tmp/onpc-test-artifacts-v6dmdqn1`. Scoped whitespace checks passed.

## Fourth guarded attempt

New locally qualified observability justified this attempt; no unchanged retry.
`tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-v6dmdqn1`:
handle **72085**, **exit 1**, **1040.664s**. Dispatcher prerequisites also passed
526 tests and 3 subtests in 5.13s. No checkout edits occurred from build through
terminal collection and cleanup.

| Evidence | Location |
| --- | --- |
| Terminal result and preservation | `/tmp/onpc-graphical-smoke-4fjuw_03/result.json` |
| Refusal persisted before worker failure | `/tmp/onpc-e2e-evidence-kiwa_szh/event-000023.json` |
| Ordered qualification checkpoints | `/tmp/onpc-e2e-evidence-kiwa_szh` |
| Worker failure and cleanup | `/tmp/onpc-e2e-evidence-oix69vct/worker-result.json` |
| Fixed prompt flags | `/tmp/onpc-graphical-smoke-4fjuw_03/testresults/smoke-15.txt` |

Source SHA256: `76ce3f68e262813a209331e8a2fedcdf4c49d928e2ddef594f4d3dd6a51db9e7`.
Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Worker: `worker-a7b195bc957c4889a657afe8a38f073e`.

Real serial login, package absence, assets and boot checks passed. The prompt
timed out again. Fixed flags observed command prefix/tail/Enter and Readline
paste-mode-off; recognized prompt/error/completion flags remained false.
The new observation returned **`getty-terminal`**. Getty leader validity and
its session check passed; its `/proc` terminal field did not validate as the
expected serial device. Foreground, sudo identity/ancestry and terminal echo
checks were not reached. This does not prove sudo execution or identify the
actual terminal field value. No sudo password was sent.

Checkpoint 23 records `stage-rejected`, active stage `install-password`, and
`installation_diagnostic.recipient_refusal=getty-terminal`; the terminal result
retains it. Infrastructure is `e2e:worker-execution-failed`; product and aggregate
collection are `not-run`. Finalization additionally logged the generic
`unexpected-failure-or-interruption`, without replacing the terminal category.
Prior three prompt attempts remain failed. **Four expensive attempts on this
blocker; one this slice. No unchanged fifth attempt.**

## Cleanup and next boundary

Worker stopped and callback closed; backend status is null because the
controller stopped it. Normal journey shutdown was not reached. Outer cleanup
powered off, restored and verified the retained baseline; cleanup passed,
lease phase is complete, host/source preservation passed, and the command
exited and released its lease. All session commands exited and results were
collected. No screenshot export, recovery, policy denial or Polkit denial.

Initial guessed source filenames were absent; scoped discovery found the owning
modules. The default 8000-byte artifact read truncated checkpoint JSON; a bounded
32000-byte read recovered it. Full-run stdout was also truncated; focused
artifact reads established terminal and checkpoint fields without rerunning
tests or exporting private data. Preparation/test/cleanup measured
511.727/324.760/73.489s; final provenance collection extended the run to
17.3 minutes. The slice budget was a review boundary; owned finalization finished.

Next: diagnose the stock getty/login leader's terminal association after login.
Distinguish no controlling terminal from a different terminal or read failure
using fixed safe observations; establish a supported, identity-bound route to
the actual fixture shell/foreground recipient before changing the proof.
Do not simply remove the getty-terminal check or weaken password/echo guards.
Use local behavioral fixtures and current supported OS contracts, then fresh
artifacts and isolated prerequisites for the next discriminating guarded run.
Read the changed modules above and their focused tests first.

Next settings: **`gpt-6-astra` / `high`**; model keep, effort keep. The failing
predicate is known, but post-login terminal ownership and safe recipient
discovery remain unresolved. Installation success/live refusal, final red
notice, customer reboot, layout/readiness and both startup faults remain.
Task estimates: **Unknown sessions / Unknown minutes**; four failed attempts
of 16.4–17.4 minutes do not predict those unqualified boundaries. Handoff
edits invalidate artifact reuse; build fresh inputs next time.
