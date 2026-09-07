# Task 19A ordered recording — 2026-09-07

This session implemented and tested the controller recording boundary. It did
not run a VM, install the product on the development host, or complete Task 19A.

## Delivered

- `ScenarioRecorder` records case/action starts before execution, completed
  assertions, safe continuity aliases, reviewed evidence and independent outcomes.
  Private checkpoints are new fsynced files; earlier failure evidence is retained.
- Ordered actions and assertion evidence must match the frozen inventory.
  Missing actions are never fabricated, and worker success creates no assertions.
- `run_case` checkpoints before its trusted cleanup callback, attempts cleanup
  after interruption or collection failure, and preserves the first exception.
  Cleanup can still execute after a failed action deadline.
- The worker bridge rechecks the owned provenance contract before startup and
  connects worker failures to durable scenario checkpoints before worker cleanup.
  Hook failure cannot prevent either owned resource's cleanup.
- Final validation requires the original held, complete lease. It rejects stale
  inputs and tampered report copies, including changes after the initial gate.
  Rejection records retain the original failure history. Storage failure preserves
  earlier checkpoints and the original error; it cannot guarantee a new report.

The callback/lease objects in host tests are synthetic. Git source capture,
private file persistence, secret scanning and evidence reconciliation use the
real implementations. No source logs or baseline artifacts were modified.
All 33 scenario families / 156 variants remain pending. Activation is `none`
(next test invocation), with no product integration or saved-data migration.

## Verification

29 new regressions: 27 in the recorder module and two worker-hook cases.
The final code batch passed:

```sh
tools/run-unit-tests tests/unit/test_e2e_recording_cleanup_safety.py tests/unit/test_e2e_worker_cleanup_safety.py tests/unit/test_e2e_provenance.py tests/unit/test_e2e_evidence.py tests/unit/test_e2e_runner.py -q
make check
git diff --check
```

| Check | Result | Measured test time / completion |
| --- | --- | --- |
| Focused selection | 278 passed | 2.92 s; handle 32705, exit 0 |
| Unit/contracts in `make check` | 2,046 passed | 32.30 s |
| Private-D-Bus components | 17 passed | 0.41 s |
| Syntax and stage traceability | Passed | make handle 93299, exit 0 |
| Whitespace | Passed | exit 0 |

Earlier focused iterations also passed; no expensive experiment was performed.
There was no VM preparation/test/cleanup time. Session-wide timing was not
instrumented. The full unit count includes concurrent permission-rule tests;
only the 29 cases above were added by this implementation slice.

## Verified code identities

| File | SHA-256 |
| --- | --- |
| `tests/e2e/recording.py` | `26b780939f7f348ebc11956efc9567cddf1881e70c7910ef48bc900d339df9cc` |
| `tests/e2e/e2e_worker.py` | `6e6e985ee5bd76b55cc8b23214ca204af6d385f1a032a126de25588555cdf860` |
| `tests/e2e/evidence.py` | `a9f7e9eb47e9ea352d4a0e811c90dc49f302aabc38cf3453c06048a35d01a114` |
| `tests/e2e/provenance.py` | `4dac5c7e77a450852da55c7819cac27ae97337d8aa4b1b3b41d9370774235988` |
| `tests/unit/test_e2e_recording_cleanup_safety.py` | `0171e2f24d9b70b13e2057596dcb126b54e81ec80644e1ea6e412ecb8cb05d9b` |
| `tests/unit/test_e2e_worker_cleanup_safety.py` | `0d9cf2adb8d060358c22eff3e00f90565465e25a0b9f36e54f02b5c096a215a9` |

## Next observable result

Use the active [Task 19A handoff](../Task-19.md#task-19a-continuation--2026-09-07).
The remaining boundary is live lease/callback integration and one guarded
credential-free qualification, with exactly one cleanup and provenance checks
before release. The current feasibility schedule cannot satisfy E2E-001's
pending console/matching declarations. Its diagnostic success must remain
separate from scenario acceptance. Authenticated transport and reviewed capture
production also remain Task 19A acceptance work.
