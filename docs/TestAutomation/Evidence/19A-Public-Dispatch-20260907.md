# Task 19A — public callback execution and invocation outcomes

**Solid progress:** public runnable selections now reach the guarded scenario
controller. The previous `execution-controller-unfinished` gate is removed;
all 156 repository variants remain pending and still refuse before privilege
checks. This is a completed implementation milestone with 32 new host regression
cases, not Task 19A acceptance or customer coverage.

## Completed boundary

`runner.preflight` validates safe existing artifact directories and confined
Python callback paths without executing code. The category launcher and installed
dispatcher retain their existing repeated preflight, privilege and isolated
cleanup-safety checks; no policy/setup changes are needed. `runner.main` imports
the execution controller only for a runnable selection.

`execution.attempt` stages verified assets before VM acquisition, uses the
existing lease preparation/bootstrap, captures independent source/package/
baseline inputs, and matches the exact preflight case against its frozen
contract. Each case gets an independent complete attempt. The invocation compares
all attempts' inputs, stops on the first failure, and retains unexecuted expected
case identities. Separate connections share one public libvirt event loop.

The digest-checked Python module supplies `E2E_CASES[test_id]`; its actual
callback receives the recorder and prepared context. Callback return values
never create steps, assertions or acceptance. `ScenarioContext.run_worker`
forwards the existing recorder/worker and retains actual worker, callback and
shutdown proof. Missing worker proof, records or assertions refuses acceptance.
Secrets are registered before preparation reports; callbacks use the established
same-lease credential and asset helpers in declared setup steps.

The existing `LeasedScenario` still owns only the recording bridge;
`Lease.__exit__` alone restores and releases. Preparation failures before a
recorder exists receive separate durable diagnostics. Action failure is retained
before restoration and survives later restoration/close failures. After lease
exit, the controller checks host preservation, closes its connection, verifies
the exact artifact manifest, and closes collectors. Fixed codes replace raw
exceptions. Terminal-candidate files cannot establish an invocation pass alone:
the final post-close JSON and successful exit are required. A failed collector
close or terminal write revokes the earlier candidate; unavailable storage can
leave only earlier checkpoints.

This is development-only activation on invocation (`none`), with no product,
saved-data, setup, transport, baseline or process-cleanup implementation changes.

## Verification and limitations

The synthetic declaration exists only in pytest temporary storage. Tests execute
the public entry point, actual module loader/callback, recorder, private
collector, evidence gate and real lease exit. VM operations, provenance
observations and the worker are substituted. These tests are host controller
proof, not live graphical/serial results. Existing serial/shutdown qualification
remains [separate live evidence](19A-Shutdown-20260907.md).

| Check / handle | Result / measured test time | VM preparation / test / cleanup |
| --- | --- | --- |
| Initial attempt/runner checks / 77043 | 53 passed / 1.15 s | None |
| Expanded public checks / 12333 | 99 passed, 6 failed / 1.53 s; test-wide fake UID broke real collector ownership checks | None |
| Corrected public checks / 99941 | 105 passed / 1.52 s; only the entry point's privilege check is substituted | None |
| Final focused selection / 43552 | 109 passed / 1.57 s | None |
| Final `make check` / 57489 | 2,485 unit/contracts / 43.95 s; 17 components / 0.45 s; syntax and stage traceability passed | None |
| `git diff --check` | Passed | None |

Final focused command:

```sh
tools/run-unit-tests tests/unit/test_e2e_execution_cleanup_safety.py tests/unit/test_e2e_runner.py tests/unit/test_e2e_leased_recording_cleanup_safety.py tests/unit/test_e2e_recording_credentials.py -q
```

| Runtime/test file | SHA-256 |
| --- | --- |
| `tests/e2e/execution.py` | `eb16a248596bfd3b3505fe67efa9a804406dc0fbba980bf1dc060086241a03a3` |
| `tests/e2e/runner.py` | `6ef5c2fd35c1dbf0b73757211ef850cb99c456a8fc4fa57c3fb717375f5c2794` |
| `tests/unit/test_e2e_execution_cleanup_safety.py` | `781edb5f79e23d20f080d0f17be1f01ff4537549c3025eb93b35fffc3f397eb3` |
| `tests/unit/test_e2e_runner.py` | `7dd85b5b9d0a757d8bced60c8662ab681bd6260943bf247a56024afac634df44` |
| Unchanged `tests/e2e/leased_recording.py` | `fba4a40f065b26c31f23e003699017a0cb78d795d1171af879b4b3957d60319d` |
| Unchanged `tests/e2e/e2e_worker.py` | `fd3caa0411036b23c76ccacf5ef3cc696fbc636cbbcf138e64403ee2d2dcf211` |

All command handles exited. No VM attempt, recovery, setup, snapshot, screenshot
export or process signal was initiated. Read-only `tools/test-vm status`
confirmed off (`state=5`, `id=-1`). Later edits are documentation only. No package
artifact is nominated. Test timings are exposed tool measurements; complete
session duration/token telemetry was not recorded.

## Remaining acceptance

Next session should audit the eight Task 19A deliverables against these host
proofs and the retained live transport evidence, then perform only the remaining
acceptance checks. The main unresolved acceptance question is whether the newly
connected public preparation/finalization path needs a distinct live harness
qualification beyond the existing serial controller. If it does, identify and
exercise that exact path; rerunning the unchanged serial smoke alone cannot
prove the new controller. Do not rebuild dispatch, create another cleanup owner,
repeat backend diagnosis, or mark E2E-001 ready to bypass 19B screen work.

Estimate **one substantial session / 1–2 hours** for the acceptance audit,
targeted live integration if required, and corrections; moderate-to-low
confidence. A demonstrated new live defect could require a second session.
This is lower than the previous 2–3-hour estimate because public dispatch and
failure reporting are now implemented and tested. It excludes 19B and customer
scenarios.
