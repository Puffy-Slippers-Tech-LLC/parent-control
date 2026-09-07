# Task 19A: read-only observation capability

This dev-host slice implements a previously missing scenario boundary. The
asset receipt and greeter corroboration now go through `ReadOnlyObservations`;
its two fixed guest programs have one maintained definition. Scenario-facing
observation no longer accepts arbitrary command vectors. The wrapper pins its
transport configuration, checks the held lease before and after execution,
validates exact safe output, and permanently refuses further reads after a
failure or interruption. Unknown operations never reach the transport.

This is solid implementation progress, with host verification only. It does
not accept Task 19A, transfer qualification, authentication, serial transport,
or any of the 156 pending customer variants. The originally considered secret
slice was narrowed to this prerequisite boundary after inspecting the unrestricted
transport used by graphical observation. Private credential staging and capture
handling remain the next independent implementation result.

## Verification and inputs

Base revision: `fafe57e`, plus the exact bytes below. Initial test collection
caught a reserved pytest parameter name; the first executable pass caught an
existing smoke mock/error expectation that needed the new contract. Both were
corrected before the final results. No failed VM evidence was replaced.

| Experiment | Result | Timing / operation state |
| --- | --- | --- |
| `tools/run-unit-tests tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_asset_transfer_cleanup_safety.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py -q` | 124 passed, including 41 new capability cases; actual asset/greeter programs also exercised by existing tests | 1.70 seconds; handle 25855 exited 0 |
| `make check` | 2,210 unit/contracts; 17 private-D-Bus components; syntax and stage traceability passed | Unit 36.50 seconds, components 0.33 seconds; handle 57433 exited 0 |
| `git diff --check` | Passed | Rechecked after handoff edits |
| Preparation / VM / cleanup | No setup, build, VM start, transfer attempt or privileged cleanup | Approximately 20–25 minutes active implementation/review; no usage telemetry exposed |

Only documentation changed after these runtime checks. A future package-bearing
run needs fresh verified artifacts because documentation is currently part of
source provenance. No reusable package artifact is nominated.

| Tested input | SHA-256 |
| --- | --- |
| `tests/e2e/asset_transfer.py` | `e8c5b2973e0c3c1398aa99baf206da5f59db00df143702261f174b9cb7df3e96` |
| `tests/e2e/guest_observations.py` | `4d367274a11f1669cd5f48bb798bcb13bbd3b7d2562cc3ce5108756158a9b6ce` |
| `tests/e2e/observation_transport.py` | `6d75f8d2913ce97c5f459f34e0da5c61ba0b5de3a9400596d3ccfff392354c3e` |
| `tests/integration/check_graphical_smoke.py` | `6d7204a6e098ced063e67fa774afdf2e0bafa3724c60aba9775e1f5c80724283` |
| `tests/unit/test_e2e_asset_transfer_cleanup_safety.py` | `113a3e2168b2d682b2a0998f6204466f2017b6abaf9ef135ff6cf720aaac0c86` |
| `tests/unit/test_e2e_observation_transport.py` | `dfead0fcd62cc49c1394a78882e82337e5cae852eae403b820a9215e035e8df9` |
| `tests/unit/test_graphical_smoke.py` | `9e54e15eb739a9dccc7a11ee41b03165f18dd0cdbb9ece7bc6db3c34ef3e92be` |
| `tests/unit/test_graphical_smoke_cleanup_safety.py` | `1c601400b7456225d644df098d3280cf37ae46f712d78ee70b655ae446bf5310` |

## Next boundary and anti-loop rule

Implement private os-autoinst secret-variable staging and the masked-prompt,
password-input and capture-failure contract; consult `e2e_worker.run_distribution`,
`PrivateCollector`, the maintained public password API, and the prior
[secret findings](19P-Backend-Preflight-2026-09-06.md#capture-cleanup-and-downstream-prerequisites).
Host refusal/interruption checks can advance without waiting for other editors.
Do not open credentials to the current credential-free distribution before that
contract works. A supported console definition and a harmless serial command
still require implementation and a real success/failure attempt.

Transfer expensive-attempt count remains four; no new attempt occurred here.
The [prior attempt](19A-Asset-Observation-20260907.md) failed on concurrent source
edits. Before the next live attempt, establish a source-stable window, complete
local edits, build fresh artifacts, and use the guarded transfer qualification
route once. Verify the new observation route and offline/booted receipts in that
same attempt. If editing remains active, continue the independent credential
work instead of rebuilding into the same provenance refusal.

All owned test commands finished. No VM or lease operation was started here;
the last VM-off observation remains the prior session's 23:07 UTC check, not a
new observation. No logs/artifacts were removed or modified.
