# Task 19A — scenario recording across owned cleanup

**Solid progress:** the recorder can now forward the proven authenticated serial
worker and finalize ordered scenario evidence through the real lease lifecycle.
This session added 43 executable host regressions. **19A remains open:** the
public scenario dispatcher still refuses with `e2e:execution-controller-unfinished`;
all 156 inventory variants remain pending. No customer or live bridge acceptance
is claimed.

## Boundary resolved

The earlier synchronous `ScenarioRecorder.run_case` expected cleanup to complete
inside its cleanup callback. The real `Lease.__exit__` performs restoration only
after control leaves its body. Calling `finish()` from that recorder callback
would introduce a second cleanup owner; completing records before exit would
report restoration before it happened. `leased_recording.LeasedScenario` connects
these existing interfaces without changing VM operations.

Attach it after preparation and independent provenance capture, under the
original held lease, with one exact selected case. It refuses an existing
finalizer, unprepared/running/released leases, missing ledger, and stale inputs.
It checks ownership/provenance again before scenario code executes. The recorder
persists actual actions and starts the outer cleanup step before the lease exits.
After the lease's sole restoration attempt, the finalizer checks the original
descriptor/run/domain/ledger identities, complete state, fresh off-state guard,
and provenance. Its trusted read/report callback collects actual preservation
results; it never restores or releases. The recorder ends cleanup and validates
the private evidence twice around the acceptance copy, while the lease is held.
The result accessor also refuses failed release recorded by the original ledger.
The public invocation must still account for connection-close/report failures.

`ScenarioRecorder.run_worker` now forwards `credentials` and `serial`, requires
actual same-lease `FixtureCredentials` provisioning, and checks that every worker
secret was in the scenario collector's original frozen registry. The collector
cannot register a new secret retroactively. Unprovisioned, foreign, running,
released, invalid and unregistered credentials refuse before worker startup and
latch scenario failure. Tests exercise the real credential provisioner with fake
offline operations, the real collector and encoded secret exclusions. The worker
itself retains its existing same-lease check.

These are development-only Python adapters, activated on next invocation
(`none`). No product, setup policy, saved-data schema, VM transport or shutdown
implementation changed in this slice.

## Verification

The lifecycle tests execute the real `Lease.__exit__`, recorder, private collector
and evidence contract. Only VM operations and provenance observations are
substituted. Passing evidence requires all actual synthetic actions/assertions;
a returned worker pass creates none. Failure coverage includes interruption,
restoration, identity replacement before execution and finalization, checkpoint
writes, off-state/provenance/preservation checks, late validation and release.
The temporary test inventory never changes repository scenario readiness.

| Check / handle | Result / measured test time | VM preparation / execution / cleanup |
| --- | --- | --- |
| Initial focused selection / 27053 | 78 passed, 5 failed / 1.35 s. Two assertions needed the distinct interruption code; three existing recorder tests exposed an import-order dependency. | None |
| Corrected focused selection / 59893 | 95 passed / 1.39 s | None |
| Final four-module selection / 40357 | 104 passed / 1.41 s | None |
| Final `make check` / 42383 | 2,453 unit/contracts / 43.47 s; 17 components / 0.48 s; syntax and stage traceability passed | No VM |
| `git diff --check` | Passed after the final documentation handoff | None |

The final focused command was:

```sh
tools/run-unit-tests tests/unit/test_e2e_leased_recording_cleanup_safety.py tests/unit/test_e2e_recording_credentials.py tests/unit/test_e2e_recording_cleanup_safety.py tests/unit/test_e2e_runner.py -q
```

Final runtime/test SHA-256 identities:

| File | SHA-256 |
| --- | --- |
| `tests/e2e/leased_recording.py` | `fba4a40f065b26c31f23e003699017a0cb78d795d1171af879b4b3957d60319d` |
| `tests/e2e/recording.py` | `ae929a52d32d7d59c2ee2ae25e9c64975ba623a38c44b7a24f2046fa2f7a08de` |
| `tests/e2e/private_artifacts.py` | `32060e61b89b7c9c59ccc61ebd88701b6f0367e06c6badf306b6187a225bbe7b` |
| `tests/unit/test_e2e_leased_recording_cleanup_safety.py` | `8682bb053f4fa128bc262754153e9ee4f64e6c2314d0717e1d1734a5c003a778` |
| `tests/unit/test_e2e_recording_credentials.py` | `187d5d5137096e2880ebd69c55677ea38fbe50c9a105d1946463e0b47311c26b` |
| `tests/unit/test_e2e_recording_cleanup_safety.py` | `f6f71dfad3139f3b8cc8a6184b7348b495b8a5a0e44f41dd594082e2f22428bd` |

All command handles exited. Read-only `tools/test-vm status` confirmed `state=5`,
`id=-1`. No VM attempt, reset, setup, screenshot export or process cleanup was
started; no operation needs recovery. Existing user changes were preserved.
The interrupted portion of this session had performed only reads. No token or
complete session-duration telemetry was available; the table records exposed
test timings, not an invented total. Later changes are documentation only.

## Next observable result

Connect `runner.preflight/main` to public guarded execution using this bridge,
actual scenario callbacks, preparation-failure evidence, and final invocation
reporting. Keep exact selection/provenance and pending-case refusal. Reuse the
[proven serial and shutdown path](19A-Shutdown-20260907.md); no repeated diagnosis
is justified by the new chat. Host tests should exercise public dispatch through
synthetic temporary declarations before any necessary live qualification.

The session completed the recorder/lease dependency of the intended public
wiring; it did not remove the public gate. Remaining **19A: 1–2 substantial
sessions / roughly 2–3 hours**, moderate-to-low confidence, for dispatch and
final acceptance/corrections. This excludes 19B and customer scenarios. The
estimate remains close to the previous forecast because the cleanup timing and
secret-registry integration needed their own verified slice.
